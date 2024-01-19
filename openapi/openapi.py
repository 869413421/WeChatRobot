import re

import requests


class OpenAPIHandler:
    @staticmethod
    def request_api(method, url, params=None, is_json=True):
        try:
            if method == 'GET':
                response = requests.get(url, params=params, verify=False)
            elif method == 'POST':
                response = requests.post(url, json=params, verify=False)
            else:
                raise ValueError("Unsupported method. Only GET and POST are supported.")

            response.raise_for_status()  # 检查请求是否成功

            # 返回 JSON 格式的响应数据
            if is_json:
                return response.json()
            else:
                return response.text

        except requests.RequestException as e:
            print("Error fetching data:", e)
        except ValueError as e:
            print("Error in request:", e)
        except Exception as e:
            print("An error occurred:", e)

    def todayInHistory(self):
        """历史上的今天"""
        url = "https://api.oick.cn/lishi/api.php"
        return self.request_api("GET", url)

    def tiTokGirlVideo(self):
        """抖音美女视频"""
        url = "https://v.api.aa1.cn/api/api-girl-11-02/index.php?type=json"
        return self.request_api("GET", url)

    def dog(self):
        """舔狗日记"""
        url = "https://v.api.aa1.cn/api/tiangou/index.php"
        res = self.request_api("GET", url, is_json=False)
        # 去除html标签
        res = re.sub(r'<[^>]+>', '', res)
        res = res.strip()
        return res

    def weather(self, city):
        """天气预报"""
        url = "https://www.apii.cn/api/weather/?city=%s" % city
        return self.request_api("GET", url)

    def search_movie(self, movie_name):
        """搜索电影"""
        url = "https://www.662688.xyz/api/get_zy?keyword=%s" % movie_name
        return self.request_api("GET", url)


# 示例使用
if __name__ == "__main__":
    api = OpenAPIHandler()
    # reuslt = api.todayInHistory()
    result = api.search_movie("繁华")
    if len(result["data"]) == 0:
        rsp = "🤔🤔🤔🤔🤔抱歉，没有找到任何相关资源。🤔🤔🤔🤔🤔"
    else:
        movie_str = ""
        for i in result['data'][:50]:
            movie_str += "【%s】(%s)\n" % (i['title'], i['url'])
        rsp = "😎😎😎😎😎为您找到以下资源😎😎😎😎😎：\n%s" % movie_str
    print(rsp)
    data = result['data'][:3]
    print(data)
