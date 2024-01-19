#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import signal
from argparse import ArgumentParser

from wcferry import Wcf

from configuration import Config
from constants import ChatType
from robot import Robot, __version__


def weather_report(robot: Robot) -> None:
    """模拟发送天气预报
    """

    # 获取接收人
    receivers = ["filehelper"]

    # 获取天气，需要自己实现，可以参考 https://gitee.com/lch0821/WeatherScrapy 获取天气。
    report = "这就是获取到的天气情况了"

    for r in receivers:
        robot.sendTextMsg(report, r)
        # robot.sendTextMsg(report, r, "notify@all")   # 发送消息并@所有人


def main(chat_type: int):
    config = Config()
    wcf = Wcf(debug=True)

    def handler(sig, frame):
        wcf.cleanup()  # 退出前清理环境
        exit(0)

    signal.signal(signal.SIGINT, handler)

    robot = Robot(config, wcf, chat_type)
    robot.LOG.info(f"WeChatRobot【{__version__}】成功启动···")

    # 接收消息
    robot.enableReceivingMsg()  # 加队列

    # 历史上的今天
    robot.onEveryTime("08:00", robot.todayInHistory)

    # 发送新闻
    robot.onEveryTime("08:00", robot.newsReport)

    # 发送摸鱼
    robot.onEveryTime("10:00", robot.moyu)

    # 每天 16:30 提醒发日报周报月报
    # robot.onEveryTime("17:30", ReportReminder.remind, robot=robot)

    # 让机器人一直跑
    robot.keepRunningAndBlockProcess()


if __name__ == "__main__":
    # import httpx
    # from openai import OpenAI
    # from pathlib import Path
    #
    # client = OpenAI(
    #     api_key="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",
    #     http_client=httpx.Client(
    #         proxies="http://127.0.0.1:10809",
    #     ),
    # )
    #
    # speech_file_path = Path(__file__).parent / "speech.mp3"
    # response = client.audio.speech.create(
    #     model="tts-1",
    #     voice="nova",
    #     input="我爱你，爱着你就像老鼠爱大米。"
    # )
    #
    # response.stream_to_file(speech_file_path)
    # exit()

    parser = ArgumentParser()
    parser.add_argument('-c', type=int, default=0, help=f'选择模型参数序号: {ChatType.help_hint()}')
    args = parser.parse_args().c
    main(args)
