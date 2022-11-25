import requests
from bs4 import BeautifulSoup
from flask import Flask, request
import py_eureka_client.eureka_client as eureka_client
import time
import nest_asyncio
nest_asyncio.apply()

boj_url = 'https://www.acmicpc.net/'
language_numbers = {'Python': '28', 'Java': '93'}  # jdk 11

# eureka_client.init(eureka_server="http://172.17.0.1:8761/eureka",
#                    app_name="search-service",
#                    instance_host="172.17.0.1",
#                    instance_port=7001)

app = Flask(__name__)


@app.route("/search/<number>", methods=["GET"])
def get_problem_info(number: str):
    url = boj_url + 'problem/' + number
    response = requests.get(url)
    response.raise_for_status()  # OK 아닌 경우 오류
    soup = BeautifulSoup(response.text, "lxml")
    problem_description = soup.find('div', attrs={"id": "problem_description"})
    problem_input = soup.find('div', attrs={"id": "problem_input"})
    problem_output = soup.find('div', attrs={"id": "problem_output"})
    i = 1
    samples = []
    samples_text = []
    while soup.find('pre', attrs={"id": "sample-input-" + str(i)}):
        sample_input = soup.find('pre', attrs={"id": "sample-input-" + str(i)})
        sample_output = soup.find('pre', attrs={"id": "sample-output-" + str(i)})
        samples.append({"input": str(sample_input), "output": str(sample_output)})
        sample_input_text = soup.find('pre', attrs={"id": "sample-input-" + str(i)}).text
        sample_output_text = soup.find('pre', attrs={"id": "sample-output-" + str(i)}).text
        samples_text.append({"input": str(sample_input_text), "output": str(sample_output_text)})
        i += 1
    return {"problem_description": str(problem_description), "problem_input": str(problem_input),
            "problem_output": str(problem_output), "samples": samples, "samples_text": samples_text}

'''
{
    "id": "jamjoa",
    "boj_autologin": "3c176...",
    "language":"Python",
    "source":"a,b = map(int, input().split())\nprint(a+b)"
}
'''
@app.route("/search/submit/<number>", methods=['POST'])
def submitCodeToBoj(number: str):
    req = request.get_json()

    headers_dict = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
    }
    response = requests.get('https://www.acmicpc.net', headers=headers_dict)

    cookies_dict = {
        'bojautologin': req['boj_autologin'],
        'OnlineJudge': response.cookies.get_dict()['OnlineJudge']
    }

    url = boj_url + 'submit/' + number
    response = requests.get(url, headers=headers_dict, cookies=cookies_dict)

    html = response.text
    soup = BeautifulSoup(html, 'html.parser')
    input_tags = soup.select('input')

    if input_tags[1]['name'] == 'login_user_id':
        print('Login required')
        return {"result": "로그인 토큰을 확인해주세요."}

    csrf_key = ""
    for i in input_tags:
        if i['name'] == 'csrf_key':
            csrf_key = i['value']

    payload = {
        'problem_id': number,
        'language': language_numbers[req['language']],
        'code_open': 'open',
        'source': req['source'],
        'csrf_key': csrf_key
    }
    response = requests.post(url, headers=headers_dict, data=payload, cookies=cookies_dict)
    if response.status_code != 200:
        return {"result": "제출에 실패했습니다."}

    url = boj_url + 'status?user_id=' + req['id']
    response = requests.get(url)
    response.raise_for_status()  # OK 아닌 경우 오류
    soup = BeautifulSoup(response.text, "lxml")
    rows = soup.select('tbody tr')
    submitted_number = -1
    for row in rows:
        if row.find('a', attrs={"class": "problem_title"}).text == number:
            submitted_number = row.find('td').text
            break
    print(submitted_number)

    success = False
    judge_result = ""
    while True:
        response = requests.get(url, "lxml")
        response.raise_for_status()  # OK 아닌 경우 오류
        soup = BeautifulSoup(response.text, "lxml")
        row = soup.find('tr', attrs={"id": "solution-" + submitted_number})
        result = row.find('span', attrs={"class": "result-text"})
        result_attrs = result.attrs
        if 'result-compile' in result_attrs['class'] or 'result-judging' in result_attrs['class']:
            print('채점 중')
            time.sleep(3)
            continue
        else:
            if 'result-ac' in result_attrs['class']:
                judge_result = '맞았습니다'
                success = True
            elif 'result-wa' in result_attrs['class']:
                judge_result = '틀렸습니다'
            else:
                judge_result = result.text
            print(judge_result)
            break
    return {"success": success, "result": judge_result}


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=7001)
    # Use a production WSGI server error
    # 플라스크는 한 요청만 처리한다. 실제 개발을 위해서는 WSGI Server가 필요하다.
    # 플라스크도 기본적으로 Werkzeung를 WSGI Middleware로 사용하지만, 단순한 개발용 서버로 다른 서버를 사용할 필요가 있다.
    # 그 중 하나가 Gunicorn이다. pip를 통해 설치할 수 있다.
    # gunicorn을 통해 실행 시 worker process나 worker thread개수를 설정할 수 있다.
    # CPU bound한 작업을 할 경우 worker 개수, IO bound한 작업일 경우 thread 를 신경 쓰는 게 좋다.
    # gunicorn --workers 4 --bind 0.0.0.0:7001 main:app
    # 개발 시엔 --reload 포함
    # gunicorn --threads 4 --worker-class gevent --bind 0.0.0.0:7001 main:app
