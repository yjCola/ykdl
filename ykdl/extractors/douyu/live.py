#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ykdl.util.html import get_content, add_header
from ykdl.util.match import match1, matchall
from ykdl.util.jsengine import JSEngine, javascript_is_supported
from ykdl.extractor import VideoExtractor
from ykdl.videoinfo import VideoInfo
from ykdl.compact import urlencode

import time
import json
import uuid


douyu_match_pattern = [ 'class="hroom_id" value="([^"]+)',
                        'data-room_id="([^"]+)'
                      ]
class Douyutv(VideoExtractor):
    name = u'斗鱼直播 (DouyuTV)'

    stream_ids = ['4k', 'BD', 'TD', 'HD', 'SD']
    profile_2_id = {
        u'蓝光10M': '4k',
        u'蓝光4M': 'BD',
        u'超清': 'TD',
        u'高清': 'HD',
        u'流畅': 'SD'
     }

    def prepare(self):
        assert javascript_is_supported, "No JS Interpreter found, can't parse douyu live!"

        info = VideoInfo(self.name, True)
        add_header("Referer", 'https://www.douyu.com')

        html = get_content(self.url)
        self.vid = match1(html, 'room_id\s*=\s*(\d+);', '"room_id.?":(\d+)', 'data-onlineid=(\d+)')
        info.title = match1(html, 'Title-headlineH2">([^<]+)<')
        info.artist = match1(html, 'Title-anchorName" title="([^"]+)"')
        if info.title and info.artist:
            info.title = '{} - {}'.format(info.title, info.artist)

        html_content = get_content('https://www.douyu.com/swf_api/homeH5Enc?rids=' + self.vid)
        data = json.loads(html_content)
        assert data['error'] == 0, data['msg']
        js_enc = data['data']['room' + self.vid]

        try:
            # try load local .js file first
            # from https://cdnjs.com/libraries/crypto-js
            from pkgutil import get_data
            js_md5 = get_data(__name__, 'crypto-md5.js')
            if isinstance(js_md5, bytes):
                js_md5 = js_md5.decode()
        except IOError:
            js_md5 = get_content('https://cdnjs.cloudflare.com/ajax/libs/crypto-js/3.1.9-1/crypto-js.min.js')

        js_ctx = JSEngine(js_md5)
        js_ctx.eval(js_enc)
        did = uuid.uuid4().hex
        tt = str(int(time.time()))
        ub98484234 = js_ctx.call('ub98484234', self.vid, did, tt)
        self.logger.debug('ub98484234: ' + ub98484234)
        params = {
            'v': match1(ub98484234, 'v=(\d+)'),
            'did': did,
            'tt': tt,
            'sign': match1(ub98484234, 'sign=(\w{32})'),
            'cdn': '',
            'rate': 0,
            'iar': 1,
            'ive': 0
        }

        data = urlencode(params)
        if not isinstance(data, bytes):
            data = data.encode()
        html_content = get_content('https://www.douyu.com/lapi/live/getH5Play/{}'.format(self.vid), data=data)
        self.logger.debug(html_content)

        live_data = json.loads(html_content)
        assert live_data['error'] == 0, live_data['msg']

        live_data = live_data["data"]
        real_url = '{}/{}'.format(live_data['rtmp_url'], live_data['rtmp_live'])
        rate_2_profile = dict((rate['rate'], rate['name']) for rate in live_data['multirates'])
        video_profile = rate_2_profile[live_data['rate']]
        stream = self.profile_2_id[video_profile]
        info.stream_types.append(stream)
        info.streams['TD'] = {
            'container': 'flv',
            'video_profile': video_profile,
            'src' : [real_url],
            'size': float('inf')
        }

        return info

    def prepare_list(self):

        html = get_content(self.url)
        return matchall(html, douyu_match_pattern)

site = Douyutv()
