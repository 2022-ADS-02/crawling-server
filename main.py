import requests
from bs4 import BeautifulSoup
import uvicorn
from fastapi import FastAPI

base_url = 'https://www.acmicpc.net/problem/'

app = FastAPI()


@app.get("/search/{number}")
async def get_problem_info(number: str):
    url = base_url + number
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


if __name__ == '__main__':
    uvicorn.run("main:app", port=7000, reload=True)
