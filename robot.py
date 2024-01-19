# -*- coding: utf-8 -*-

import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from queue import Empty
from threading import Thread

import requests
from wcferry import Wcf, WxMsg

from base.func_bard import BardAssistant
from base.func_chatglm import ChatGLM
from base.func_chatgpt import ChatGPT
from base.func_chengyu import cy
from base.func_news import News
from base.func_tigerbot import TigerBot
from base.func_xinghuo_web import XinghuoWeb
from configuration import Config
from constants import ChatType
from dbtool import MysqlFactor
from job_mgmt import Job

__version__ = "39.0.10.1"

from openapi.openapi import OpenAPIHandler


class Robot(Job):
    """个性化自己的机器人
    """

    def __init__(self, config: Config, wcf: Wcf, chat_type: int) -> None:
        self.wcf = wcf
        self.config = config
        self.LOG = logging.getLogger("Robot")
        if wcf:
            self.wxid = self.wcf.get_self_wxid()
            self.allContacts = self.getAllContacts()
        db = MysqlFactor().create(config.DB, pool=False, log_enabled=True)
        self.db = db
        self.openapi = OpenAPIHandler()

        if ChatType.is_in_chat_types(chat_type):
            if chat_type == ChatType.TIGER_BOT.value and TigerBot.value_check(self.config.TIGERBOT):
                self.chat = TigerBot(self.config.TIGERBOT)
            elif chat_type == ChatType.CHATGPT.value and ChatGPT.value_check(self.config.CHATGPT):
                self.chat = ChatGPT(self.config.CHATGPT)
            elif chat_type == ChatType.XINGHUO_WEB.value and XinghuoWeb.value_check(self.config.XINGHUO_WEB):
                self.chat = XinghuoWeb(self.config.XINGHUO_WEB)
            elif chat_type == ChatType.CHATGLM.value and ChatGLM.value_check(self.config.CHATGLM):
                self.chat = ChatGLM(self.config.CHATGLM)
            elif chat_type == ChatType.BardAssistant.value and BardAssistant.value_check(self.config.BardAssistant):
                self.chat = BardAssistant(self.config.BardAssistant)
            else:
                self.LOG.warning("未配置模型")
                self.chat = None
        else:
            if TigerBot.value_check(self.config.TIGERBOT):
                self.chat = TigerBot(self.config.TIGERBOT)
            elif ChatGPT.value_check(self.config.CHATGPT):
                self.chat = ChatGPT(self.config.CHATGPT)
            elif XinghuoWeb.value_check(self.config.XINGHUO_WEB):
                self.chat = XinghuoWeb(self.config.XINGHUO_WEB)
            elif ChatGLM.value_check(self.config.CHATGLM):
                self.chat = ChatGLM(self.config.CHATGLM)
            elif BardAssistant.value_check(self.config.BardAssistant):
                self.chat = BardAssistant(self.config.BardAssistant)
            else:
                self.LOG.warning("未配置模型")
                self.chat = None

        self.LOG.info(f"已选择: {self.chat}")

    @staticmethod
    def value_check(args: dict) -> bool:
        if args:
            return all(value is not None for key, value in args.items() if key != 'proxy')
        return False

    def toAt(self, msg: WxMsg) -> bool:
        """处理被 @ 消息
        :param msg: 微信消息结构
        :return: 处理状态，`True` 成功，`False` 失败
        """
        self.LOG.info(f"接收到消息:{msg.content}")
        cmd = re.sub(r"^@.*?[\u2005|\s]", "", msg.content).replace(" ", "")
        if cmd == "tiktok":
            sendPath = self.getAndSaveTiTokGirlVideo()
            self.LOG.info(f"发送视频:{sendPath},到群聊:{msg.roomid}")
            self.wcf.send_file(sendPath, msg.roomid)
            return True

        return self.toChitchat(msg)

    def toChengyu(self, msg: WxMsg) -> bool:
        """
        处理成语查询/接龙消息
        :param msg: 微信消息结构
        :return: 处理状态，`True` 成功，`False` 失败
        """
        status = False
        texts = re.findall(r"^([#|?|？])(.*)$", msg.content)
        # [('#', '天天向上')]
        if texts:
            flag = texts[0][0]
            text = texts[0][1]
            if flag == "#":  # 接龙
                if cy.isChengyu(text):
                    rsp = cy.getNext(text)
                    if rsp:
                        self.sendTextMsg(rsp, msg.roomid)
                        status = True
            elif flag in ["?", "？"]:  # 查词
                if cy.isChengyu(text):
                    rsp = cy.getMeaning(text)
                    if rsp:
                        self.sendTextMsg(rsp, msg.roomid)
                        status = True

        return status

    def toChitchat(self, msg: WxMsg) -> bool:
        """闲聊，接入 ChatGPT
        """
        send_image = False
        q = re.sub(r"@.*?[\u2005|\s]", "", msg.content).replace(" ", "")
        if not self.chat:  # 没接 ChatGPT，固定回复
            rsp = "你@我干嘛？"
        else:  # 接了 ChatGPT，智能回复
            if q.startswith("画图"):
                send_image = True
                rsp = q[2:]
            elif q.startswith("找资源"):
                result = self.openapi.search_movie(q[3:].strip())
                if len(result["data"]) == 0:
                    rsp = "🤔🤔🤔抱歉，没有找到任何相关资源。"
                else:
                    movie_str = ""
                    for i in result['data'][:50]:
                        movie_str += "【%s】(%s)\n" % (i['title'], i['url'])
                    rsp = "😍😍😍找到以下资源😍😍😍：\n请复制链接到浏览器打开(非微信浏览器)\n%s" % movie_str
            else:
                if q.startswith("舔我"):
                    rsp = self.openapi.dog()
                else:
                    rsp = self.chat.get_answer(q, (msg.roomid if msg.from_group() else msg.sender))
        if rsp:
            if msg.from_group():
                if send_image:
                    self.sendImageMsg(rsp, msg.roomid)
                    return True

                if self.config.SEND_AUDIO:
                    self.sendAudioMsg(rsp, msg.roomid)
                else:
                    self.sendTextMsg(rsp, msg.roomid, msg.sender)
            else:
                if send_image:
                    self.sendImageMsg(rsp, msg.sender)
                    return True

                if self.config.SEND_AUDIO:
                    self.sendAudioMsg(rsp, msg.sender)
                else:
                    self.sendTextMsg(rsp, msg.sender)
            return True
        else:
            self.LOG.error(f"无法从 ChatGPT 获得答案")
            return False

    def processMsg(self, msg: WxMsg) -> None:
        """当接收到消息的时候，会调用本方法。如果不实现本方法，则打印原始消息。
        此处可进行自定义发送的内容,如通过 msg.content 关键字自动获取当前天气信息，并发送到对应的群组@发送者
        群号：msg.roomid  微信ID：msg.sender  消息内容：msg.content
        content = "xx天气信息为："
        receivers = msg.roomid
        self.sendTextMsg(content, receivers, msg.sender)
        """

        sql = "INSERT INTO messages (id, type, xml, sender, roomid, content, thumb, extra) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        val = (msg.id, msg.type, msg.xml, msg.sender, msg.roomid, msg.content, msg.thumb, msg.extra)
        self.db.execute(sql, val)

        # 群聊消息
        if msg.from_group():
            # 如果在群里被 @
            if msg.roomid not in self.config.GROUPS:  # 不在配置的响应的群列表里，忽略
                return

            if msg.is_at(self.wxid):  # 被@
                self.toAt(msg)

            else:  # 其他消息
                self.toChengyu(msg)

            return  # 处理完群聊信息，后面就不需要处理了

        # 非群聊信息，按消息类型进行处理
        if msg.type == 37:  # 好友请求
            self.autoAcceptFriendRequest(msg)

        elif msg.type == 10000:  # 系统信息
            self.sayHiToNewFriend(msg)

        elif msg.type == 0x01:  # 文本消息
            # 让配置加载更灵活，自己可以更新配置。也可以利用定时任务更新。
            if msg.from_self():
                if msg.content == "^更新$":
                    self.config.reload()
                    self.LOG.info("已更新")
            else:
                self.toChitchat(msg)  # 闲聊

    def onMsg(self, msg: WxMsg) -> int:
        try:
            self.LOG.info(msg)  # 打印信息
            self.processMsg(msg)
        except Exception as e:
            self.LOG.error(e)

        return 0

    def enableRecvMsg(self) -> None:
        self.wcf.enable_recv_msg(self.onMsg)

    def enableReceivingMsg(self) -> None:
        def innerProcessMsg(wcf: Wcf):
            while wcf.is_receiving_msg():
                try:
                    msg = wcf.get_msg()
                    self.LOG.info(msg)
                    self.processMsg(msg)
                except Empty:
                    continue  # Empty message
                except Exception as e:
                    self.LOG.error(f"Receiving message error: {e}")

        self.wcf.enable_receiving_msg()
        Thread(target=innerProcessMsg, name="GetMessage", args=(self.wcf,), daemon=True).start()

    def sendTextMsg(self, msg: str, receiver: str, at_list: str = "") -> None:
        """ 发送消息
        :param msg: 消息字符串
        :param receiver: 接收人wxid或者群id
        :param at_list: 要@的wxid, @所有人的wxid为：notify@all
        """
        # msg 中需要有 @ 名单中一样数量的 @
        ats = ""
        if at_list:
            if at_list == "notify@all":  # @所有人
                ats = " @所有人"
            else:
                wxids = at_list.split(",")
                for wxid in wxids:
                    # 根据 wxid 查找群昵称
                    ats += f" @{self.wcf.get_alias_in_chatroom(wxid, receiver)}"

        # {msg}{ats} 表示要发送的消息内容后面紧跟@，例如 北京天气情况为：xxx @张三
        if ats == "":
            self.LOG.info(f"To {receiver}: {msg}")
            self.wcf.send_text(f"{msg}", receiver, at_list)
        else:
            self.LOG.info(f"To {receiver}: {ats}\r{msg}")
            self.wcf.send_text(f"{ats}\n\n{msg}", receiver, at_list)

    def getAllContacts(self) -> dict:
        """
        获取联系人（包括好友、公众号、服务号、群成员……）
        格式: {"wxid": "NickName"}
        """
        contacts = self.wcf.query_sql("MicroMsg.db", "SELECT UserName, NickName FROM Contact;")
        return {contact["UserName"]: contact["NickName"] for contact in contacts}

    def keepRunningAndBlockProcess(self) -> None:
        """
        保持机器人运行，不让进程退出
        """
        while True:
            self.runPendingJobs()
            time.sleep(1)

    def autoAcceptFriendRequest(self, msg: WxMsg) -> None:
        try:
            xml = ET.fromstring(msg.content)
            v3 = xml.attrib["encryptusername"]
            v4 = xml.attrib["ticket"]
            scene = int(xml.attrib["scene"])
            self.wcf.accept_new_friend(v3, v4, scene)

        except Exception as e:
            self.LOG.error(f"同意好友出错：{e}")

    def sayHiToNewFriend(self, msg: WxMsg) -> None:
        nickName = re.findall(r"你已添加了(.*)，现在可以开始聊天了。", msg.content)
        if nickName:
            # 添加了好友，更新好友列表
            self.allContacts[msg.sender] = nickName[0]
            self.sendTextMsg(f"Hi {nickName[0]}，我自动通过了你的好友请求。", msg.sender)

    def newsReport(self) -> None:
        receivers = self.config.NEWS
        if not receivers:
            return

        news = News().get_important_news()
        for r in receivers:
            self.sendTextMsg(news, r)

    def moyu(self) -> None:
        receivers = self.config.NEWS
        if not receivers:
            return

        path1 = self.getAndSaveMoYu()
        path2 = self.getAndSaveMoYu(1)
        for r in receivers:
            if path1:
                self.wcf.send_file(path1, r)
            if path2:
                self.wcf.send_file(path2, r)

    def todayInHistory(self) -> None:
        receivers = self.config.TODAY
        if not receivers:
            return

        result = OpenAPIHandler().todayInHistory()
        history = result.get("result", [])
        if len(history) == 0:
            return

        historyText = [f"{item['date']} {item['title']}" for item in history]
        sendText = "历史上的今天 \n" + "\n".join(historyText)

        for r in receivers:
            self.sendTextMsg(sendText, r)

    @staticmethod
    def getAndSaveTiTokGirlVideo() -> str:
        """获取 保存tiktok 美女视频"""
        result = OpenAPIHandler().tiTokGirlVideo()
        url = result.get("mp4", "")
        if url == "":
            return ""

        # 通过URL下载视频
        # 手动添加协议部分
        full_url = 'https:' + url
        response = requests.get(full_url, stream=True)
        today = datetime.now().strftime("%Y-%m-%d")
        dirPath = os.path.join(os.path.join(os.getcwd(), "video"), today)
        if not os.path.exists(dirPath):
            os.makedirs(dirPath)

        # 毫秒时间戳字符串作为文件名
        fileName = str(int(time.time() * 1000)) + ".mp4"
        savePath = os.path.join(dirPath, fileName)
        if response.status_code == 200:
            with open(savePath, 'wb') as f:
                f.write(response.content)
            # 返回保存的路径和文件名
            return savePath
        else:
            return ""

    @staticmethod
    def getAndSaveMoYu(my_type: int = 0) -> str:
        """获取 保存摸鱼日报"""
        if my_type == 1:
            url = "https://dayu.qqsuu.cn/mingxingbagua/apis.php"
        else:
            url = "https://dayu.qqsuu.cn/moyuribao/apis.php"
        today = datetime.now().strftime("%Y-%m-%d")
        dirPath = os.path.join(os.path.join(os.getcwd(), "images"), today)
        if not os.path.exists(dirPath):
            os.makedirs(dirPath)
        fileName = str(time.time()) + ".jpg"
        savePath = os.path.join(dirPath, fileName)

        try:
            response = requests.get(url)
            if response.status_code == 200:
                with open(savePath, 'wb') as file:
                    file.write(response.content)
                return savePath
            else:
                return ""
        except Exception as e:
            print(e)
            return ""

    def sendAudioMsg(self, rsp, receiver) -> None:
        """发送语音消息"""
        filePath = self.chat.generateAudio(rsp)
        self.wcf.send_file(filePath, receiver)

    def sendImageMsg(self, rsp, receiver) -> None:
        """发送图片消息"""
        filePath = self.chat.generateImage(rsp)
        print(filePath)
        if filePath:
            self.wcf.send_file(filePath, receiver)


if __name__ == "__main__":
    config = Config()
    robot = Robot(config, None, 2)
    # robot.todayInHistory()
    # robot.newsReport()
    path = robot.getAndSaveMoYu()
    print(path)

    path = robot.getAndSaveMoYu(1)
    print(path)
