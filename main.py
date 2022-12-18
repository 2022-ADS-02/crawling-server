import jwt
import pymysql
import yaml
from os import environ
import requests
from bs4 import BeautifulSoup
from flask import Flask, request
from flask_cors import CORS
import py_eureka_client.eureka_client as eureka_client
import time
import nest_asyncio

nest_asyncio.apply()

boj_url = 'https://www.acmicpc.net/'
language_numbers = {'Python': '28', 'Java': '93'}  # jdk 11

# with open("./db/access.yaml", encoding="UTF-8") as f:
#     cfg = yaml.load(f, Loader=yaml.FullLoader)
#     db_host = cfg["db_host"]
#     db_user = cfg["db_user"]
#     db_password = cfg["db_password"]
#     db_name = cfg["db_name"]

with open("./auth/token.yaml", encoding="UTF-8") as f:
    cfg = yaml.load(f, Loader=yaml.FullLoader)
    access_key = cfg["jwt"]["secret"]["access"]

# conn = pymysql.connect(host=db_host, port=3306,
#                        user=db_user, password=db_password, db=db_name,
#                        charset="utf8", cursorclass=pymysql.cursors.DictCursor)
# curs = conn.cursor()

eureka_client.init(eureka_server="{}:8761/eureka" .format(environ.get("EUREKA_ADDRESS", "192.168.2.11")),
                   app_name="crawling-service",
                   instance_host=environ.get("CRAWLING_ADDRESS", "192.168.2.14"),
                   instance_port=7001)

app = Flask(__name__)
CORS(app, resources={r"/search/*": {"origins": "*"}})


@app.route("/search/<number>", methods=["GET"])
def get_problem_info(number: str):
    # 먼저 db 체크
    if exists(number):
        return search_db(number)

    return crawl(number)


def crawl(prlblem_id):
    url = boj_url + 'problem/' + prlblem_id
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

    crawling_result = {"problem_description": str(problem_description), "problem_input": str(problem_input),
                       "problem_output": str(problem_output), "samples": samples, "samples_text": samples_text}
    save_result(prlblem_id, crawling_result)
    return crawling_result


'''
{
    # "id": "jamjoa",
    # "boj_autologin": "3c176...",
    "language":"Python",
    "source":"a,b = map(int, input().split())\nprint(a+b)"
}
'''


@app.route("/search/submit/<number>", methods=['POST'])
def submitCodeToBoj(number: str):
    if 'Authorization' not in request.headers:
        return "토큰을 확인해주세요", 401
    token = request.headers['Authorization'].replace('Bearer', '').strip()
    decoded_token = jwt.decode(token, access_key, algorithms="HS256")
    member_id = decoded_token['id']
    boj_token = decoded_token['bojToken']
    print(token, decoded_token, member_id, boj_token)

    req = request.get_json()

    headers_dict = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
    }
    response = requests.get('https://www.acmicpc.net', headers=headers_dict)

    cookies_dict = {
        'bojautologin': boj_token,
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
    url = boj_url + 'status?user_id=' + member_id
    response = requests.get(url)
    response.raise_for_status()  # OK 아닌 경우 오류
    soup = BeautifulSoup(response.text, "lxml")
    rows = soup.select('tbody tr')
    submitted_number = ""
    for row in rows:
        problem_title = row.find('a', attrs={"class": "problem_title"})
        if problem_title and problem_title.text == number:
            submitted_number = row.find('td').text
            break
    print(submitted_number)
    if submitted_number == "":
        return "백준 아이디와 동일한 아이디가 아닙니다.", 404

    success = False
    judge_result = ""
    while True:
        response = requests.get(url, "lxml")
        response.raise_for_status()  # OK 아닌 경우 오류
        soup = BeautifulSoup(response.text, "lxml")
        row = soup.find('tr', attrs={"id": "solution-" + submitted_number})
        result = row.find('span', attrs={"class": "result-text"})
        result_attrs = result.attrs
        if 'result-compile' in result_attrs['class'] or 'result-judging' in result_attrs['class'] or 'result-wait' in result_attrs['class']:
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


def save_result(problem_id, result):
    sql = "insert into problems(problem_id, problem_description, problem_input, problem_output) " \
          "values(%s, %s, %s, %s)"
    values = (int(problem_id), result["problem_description"],
              result["problem_input"], result["problem_output"])
    curs.execute(sql, values)

    sql = "insert into samples(problem_id, input, output) " \
          "values(%s, %s, %s)"
    values = []
    for sample in result["samples"]:
        values.append((int(problem_id), sample["input"], sample["output"]))
    curs.executemany(sql, values)

    sql = "insert into samples_text(problem_id, input, output) " \
          "values(%s, %s, %s)"
    values = []
    for sample in result["samples_text"]:
        values.append((int(problem_id), sample["input"], sample["output"]))
    curs.executemany(sql, values)

    conn.commit()


def exists(problem_id):
    sql = "select exists(select * from problems where problem_id = {}) as result".format(problem_id)
    curs.execute(sql)
    result = curs.fetchone()
    return result["result"]


def search_db(problem_id: str):
    crawling_result = {"samples": [], "samples_text": []}
    sql = "select * from problems where problem_id = {}".format(problem_id)
    curs.execute(sql)
    problem = curs.fetchone()
    if problem:
        crawling_result["problem_description"] = problem["problem_description"]
        crawling_result["problem_input"] = problem["problem_input"]
        crawling_result["problem_output"] = problem["problem_output"]

    sql = "select s.input as s_input, s.output as s_output, st.input as st_input, st.output as st_output " \
          "from samples s, samples_text st " \
          "where s.problem_id = st.problem_id " \
          "and s.problem_id = {}".format(problem_id)
    curs.execute(sql)
    samples = curs.fetchone()
    while samples:
        crawling_result["samples"].append({"input": samples["s_input"], "output": samples["s_output"]})
        crawling_result["samples_text"].append({"input": samples["st_input"], "output": samples["st_output"]})
        samples = curs.fetchone()

    return crawling_result


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
