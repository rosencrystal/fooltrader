import json
import os

import scrapy
from scrapy import Request
from scrapy import signals

from fooltrader.consts import TONGHUASHUN_KDATA_HEADER
from fooltrader.items import KDataItem
from fooltrader.settings import STOCK_START_CODE, STOCK_END_CODE
from fooltrader.utils.utils import get_kdata_path_ths, get_trading_dates_path_ths, get_security_items


class StockKDataSpiderTHS(scrapy.Spider):
    name = "stock_kdata_ths"

    custom_settings = {
        'DOWNLOAD_DELAY': 10,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,

        'SPIDER_MIDDLEWARES': {
            'fooltrader.middlewares.FoolErrorMiddleware': 1000,
        },
        'DOWNLOADER_MIDDLEWARES': {
            'scrapy.downloadermiddlewares.httpauth.HttpAuthMiddleware': None,
            'scrapy.downloadermiddlewares.downloadtimeout.DownloadTimeoutMiddleware': None,
            'scrapy.downloadermiddlewares.defaultheaders.DefaultHeadersMiddleware': None,
            'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
            'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,
            'scrapy.downloadermiddlewares.redirect.MetaRefreshMiddleware': None,
            'scrapy.downloadermiddlewares.redirect.RedirectMiddleware': None,
            'scrapy.downloadermiddlewares.cookies.CookiesMiddleware': None,
            'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': None,
            'scrapy.downloadermiddlewares.stats.DownloaderStats': None,
        }
    }

    def start_requests(self):
        for item in get_security_items():
            # 设置抓取的股票范围
            if STOCK_START_CODE <= item['code'] <= STOCK_END_CODE:

                for fuquan in [True, False]:
                    data_path = get_kdata_path_ths(item, fuquan)
                    data_exist = os.path.isfile(data_path)
                    if not data_exist or True:
                        # get day k data
                        if fuquan:
                            flag = 2
                        else:
                            flag = 0
                        url = self.get_k_data_url(item['code'], flag)
                        yield Request(url=url, headers=TONGHUASHUN_KDATA_HEADER,
                                      meta={'path': data_path, 'item': item},
                                      callback=self.download_day_k_data)

                    else:
                        self.logger.info("{} kdata existed".format(item['code']))

    def download_day_k_data(self, response):
        path = response.meta['path']
        item = response.meta['item']

        kdata_json = []
        trading_dates = []
        price_json = []

        try:
            tmp_str = response.text
            json_str = tmp_str[tmp_str.index('{'):tmp_str.index('}') + 1]
            tmp_json = json.loads(json_str)

            # parse the trading dates
            dates = tmp_json['dates'].split(',')
            count = 0
            for year_dates in tmp_json['sortYear']:
                for i in range(year_dates[1]):
                    trading_dates.append('{}-{}-{}'.format(year_dates[0], dates[count][0:2], dates[count][2:]))
                    count += 1

            # parse the kdata
            tmp_price = tmp_json['price'].split(',')
            for i in range(int(len(tmp_price) / 4)):
                low_price = round(int(tmp_price[4 * i]) / 100, 2)
                open_price = round(low_price + int(tmp_price[4 * i + 1]) / 100, 2)
                high_price = round(low_price + int(tmp_price[4 * i + 2]) / 100, 2)
                close_price = round(low_price + int(tmp_price[4 * i + 3]) / 100, 2)

                price_json.append({"low": low_price,
                                   "open": open_price,
                                   "high": high_price,
                                   "close": close_price})

            volumns = tmp_json['volumn'].split(',')

            for i in range(int(tmp_json['total'])):
                k_item = KDataItem(securityId=item['id'], code=item['code'],
                                   type='stock', level='DAY',
                                   high=price_json[i]['high'],
                                   low=price_json[i]['low'],
                                   open=price_json[i]['open'],
                                   close=price_json[i]['close'],
                                   volume=int(volumns[i]),
                                   timestamp=trading_dates[i])
                kdata_json.append(dict(k_item))

        except Exception as e:
            self.logger.error('error when getting k data url={} error={}'.format(response.url, e))

        if len(kdata_json) > 0:
            try:
                with open(path, "w") as f:
                    json.dump(kdata_json, f)
            except Exception as e:
                self.logger.error('error when saving k data url={} path={} error={}'.format(response.url, path, e))
        if len(trading_dates) > 0:
            try:
                with open(get_trading_dates_path_ths(item), "w") as f:
                    json.dump(trading_dates, f)
            except Exception as e:
                self.logger.error(
                    'error when saving trading dates url={} path={} error={}'.format(response.url, path, e))

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(StockKDataSpiderTHS, cls).from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
        return spider

    def spider_closed(self, spider, reason):
        spider.logger.info('Spider closed: %s,%s\n', spider.name, reason)

    def get_k_data_url(self, code, fuquan=0):
        return 'http://d.10jqka.com.cn/v6/line/hs_{}/0{}/all.js'.format(code, fuquan)
