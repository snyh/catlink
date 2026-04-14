# xpra/xpra/client/gtk3/window/im_window_ext.py
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk
from xpra.log import Logger
from xpra.client.gtk3.window.stub_window import GtkStubWindow
from xpra.client.gtk3.window.keyboard import KeyboardWindow  # 导入KeyboardWindow
from typing import Dict, Any
import time
from typing import Callable, Optional, Tuple

import requests
import os
import sys

typedict = Dict[str, Any]
log = Logger("client", "window", "im")

RIM_SERVER=os.getenv("RIM_SERVER")

WIN32: bool = sys.platform.startswith("win")


class IMEnhancedWindow(GtkStubWindow):
    """无冲突方案：复用KeyboardWindow回调，不新增信号绑定"""
    def init_window(self, client, metadata: typedict, client_props: typedict) -> None:
        self._client = client
        self.im_context = Gtk.IMMulticontext()
        # 3. 绑定输入法完整信号集（本地程序默认绑定，缺一不可）
        self.im_context.connect("commit", self._on_im_commit)
        self.im_context.connect("preedit-start", self._on_im_preedit_start)
        self.im_context.connect("preedit-end", self._on_im_preedit_end)
        self.im_context.connect("preedit-changed", self._on_im_preedit_changed)
        self.im_context.connect("retrieve-surrounding", self._on_im_retrieve_surrounding)
        self.im_context.connect("delete-surrounding", self._on_im_delete_surrounding)
        if WIN32:
            self.im_context.set_use_preedit(False)
        self.im_setup = False
        self.when_realized("init-focus", self._setup_im)

    def _on_im_retrieve_surrounding(self, im_context):
        #log.info(f"on im retrieve surrounding")
        # TODO: set surronding
        pass
    def _on_im_delete_surrounding(self, im_context, offfset, n_chars):
        log.info(f"on im delete surrounding OFFSET:{offset} N_CHARS:{n_chars}")
        # TODO: set surronding
        pass

    def _setup_im(self):
        def _update_spot_location(x: Optional[int], y: Optional[int], error: Optional[Exception]) -> None:
            if error:
                print(f"Error: 错误：{str(error)}")
            else:
                if not self.has_focus or not self.get_window():
                    return

                if x == 0 and y == 0:
                    return

                geo = self.get_window().get_geometry()
                _x = x * self._xscale  - geo.x
                _y = y * self._yscale -  geo.y
                if WIN32:
                    _x -= geo.x
                    _y -= geo.y
                # 构造默认光标矩形（输入法只需要存在，不需要精准位置）
                cursor_rect = Gdk.Rectangle()
                cursor_rect.x = _x
                cursor_rect.y = _y
                cursor_rect.width = 1
                cursor_rect.height = 20
                #print(f"更新坐标: x:{x} y:{y}  --(s:{self._xscale})--> x:{_x} y:{_y}")
                self.im_context.set_cursor_location(cursor_rect)

        if not self.im_setup:
            self.im_context.set_client_window(self.get_window())
            self.im_context.focus_in()
            self.im_context.reset()
            self.im_setup = True
            xid = self._metadata.get("xid")
            # TODO: 这里只需要订阅一个全局坐标变化即可，不需要每个窗口都单独订阅一份
            subscribe_spots(url = f"{RIM_SERVER}/im/cursor_events?xid={xid}", callback= _update_spot_location)

    def _handle_im_events(self, _win, event) -> bool:
        return self.im_context.filter_keypress(event)

    def _on_im_preedit_start(self, im_context):
        #log.info(f"predit start, win:{self._metadata.get('id')}")
        pass

    def _on_im_preedit_end(self, im_context):
        #log.info(f"predit end, win:{self._metadata.get('id')}")
        pass

    def _on_im_preedit_changed(self, im_context):
        tstr = im_context.get_preedit_string()
        #log.info(f"predit change to: {tstr}")


    def _on_im_commit(self, im_context, text):
        """IM输入完成，发送到服务器"""
        requests.packages.urllib3.disable_warnings()
        requests.get(
            url =f"{RIM_SERVER}/im/commit",
            verify = False,
            params = {
                "text": text,
                "xid": self._metadata.get("xid"),
        })

        #log.info(f"IM提交文本：{text}")
        # if self._client and hasattr(self._window, 'wid') and self._window.wid:
        #     self._client.send_text_input(self._window.wid, text)


from threading import Thread
import threading

def subscribe_spots(url: str, callback: Callable[[Optional[int], Optional[int], Optional[Exception]], None]) -> Thread:
    """
    非阻塞订阅坐标更新（后台线程实现）
    函数调用后立即返回，不阻塞主线程
    :param url: 完整订阅地址（含 xid）
    :param callback: 回调函数 (x, y, error)
    :return: 后台线程对象（可通过 thread.stop() 尝试停止，或 thread.join() 等待结束）
    """
    def parse_coordinate(line: str) -> Tuple[Optional[int], Optional[int], Optional[Exception]]:
        """内部坐标解析函数"""
        line = line.strip()
        if not line:
            return None, None, None
        try:
            x, y = map(int, line.split(','))
            return x, y, None
        except ValueError as e:
            return None, None, ValueError(f"坐标格式无效: {line} (错误: {str(e)})")

    def _background_task() -> None:
        """后台线程执行的核心逻辑"""
        requests.packages.urllib3.disable_warnings()
        running = True
        while running:
            response: Optional[requests.Response] = None
            try:
                # 无主动超时，仅被动响应网络异常
                response = requests.get(
                    url,
                    verify = False,
                    stream=True,
                    headers={"Connection": "keep-alive"},
                )
                response.raise_for_status()

                # 逐行读取（阻塞等待数据，直到连接断开）
                for line_bytes in response.iter_lines(chunk_size=1024, decode_unicode=False):
                    if not running:  # 检测是否需要停止
                        break
                    if not line_bytes:
                        continue

                    # 解码和解析
                    try:
                        line = line_bytes.decode("utf-8")
                        x, y, err = parse_coordinate(line)
                    except UnicodeDecodeError as e:
                        err = UnicodeDecodeError(f"编码解析失败: {str(e)}")
                        x, y = None, None
                    except Exception as e:
                        err = Exception(f"读取行失败: {str(e)}")
                        x, y = None, None

                    # 调用回调（回调函数会在后台线程执行，若需主线程处理可加队列）
                    if err is not None:
                        callback(None, None, err)
                    elif x is not None and y is not None:
                        callback(x, y, None)

            except requests.exceptions.RequestException as e:
                err = requests.exceptions.RequestException(f"Error: 网络连接异常: {str(e)}")
                callback(None, None, err)
                if running:
                    print("[后台线程] 5 秒后尝试重连...")
                    time.sleep(5)
            except KeyboardInterrupt:
                break
            except Exception as e:
                err = Exception(f"Error: 未知错误: {str(e)}")
                callback(None, None, err)
                if running:
                    print("[后台线程] 5 秒后尝试重连...")
                    time.sleep(5)
            finally:
                if response is not None:
                    response.close()
                    print("[后台线程] 已关闭当前连接")

        print("[后台线程] 订阅已停止")

    # 创建并启动后台线程（守护线程，主线程退出时自动结束）
    thread = Thread(target=_background_task, daemon=True)
    thread.start()
    return thread
