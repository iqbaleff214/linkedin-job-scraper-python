import math
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from urllib.parse import quote as encode
import pandas as pd
from datetime import datetime
from time import sleep

INIT_URL = 'https://www.linkedin.com/jobs/search'
PAGE_URL = 'https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search'
POST_URL = 'https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/'

HEADERS = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"}

# PENCARIAN: keywords
#       keywords=backend
keywords = ''

# WAKTU: f_TPR
#   24 jam terakhir: r86400
#   minggu lalu: r604800
#   bulan lalu: r2592000
#       f_TPR=r86400
time_range = 'r86400'

# LOKASI: location
#   nama daerah
#       location=Indonesia
location = 'Indonesia'

# JARAK: distance
#   satuannya mil, opsi: 10, 25, 50, 75, 100
#       distance=100
distance = ''

# JENIS PEKERJAAN: f_JT
#   Purnawaktu: F
#   Paruh Waktu: CP
#   Kontrak: CC
#   Sementara: T
#   Sukarelawan: CV
#   Lainnya: F
#       f_JT=F,CP,F
job_type = []

# TEMPAT: f_WT
#   Onsite: 1
#   Remote: 2
#   Hybrid: 3
#       f_WT=1,3,2
place = []

limit_jobs = 0 # 0 => no limit

def log_error(e):
    f = open("log.txt", "a")
    
    f.write(f"{datetime.now()} ERROR {e}\n")
    f.close()

def log_info(i):
    f = open("log.txt", "a")
    f.write(f"{datetime.now()} INFO {i}\n")
    f.close()

def params(start = 0):
    return f"?keywords={encode(keywords)}&f_TPR={time_range}&location={encode(location)}&distance={distance}&f_JT={encode(','.join(job_type))}&f_WT={encode(','.join(place))}&position=1&pageNum=0&start={start}&sortBy=DD"

def job_result():
    if limit_jobs > 0:
        return limit_jobs

    uri = INIT_URL + params()
    res = requests.get(uri, headers=HEADERS)
    soup = BeautifulSoup(res.text, 'html.parser')

    job_count = soup.find('span', {'class': 'results-context-header__job-count'}).text

    return int(job_count.strip().replace(",", "").replace("+", ""))
    
def job_id_list_per_page(start):
    uri = PAGE_URL + params(start)
    res = requests.get(uri, headers=HEADERS)

    if res.status_code == 400:
        return []

    if not res.ok or len(res.history) > 0:
        log_error(f"failed to fetch page {start}")
        log_info(f"{res.status_code} {res.history}")
        sleep(0.02)
        return job_id_list_per_page(start)

    soup = BeautifulSoup(res.text, 'html.parser')

    job_ids = []
    job_list = soup.find_all('li')

    for i in range(0, len(job_list)):
        try:
            job_id = job_list[i].find('div', {'class': 'base-card'}).get('data-entity-urn').split(':')[3]
            job_ids.append(job_id)
        except:
            try:
                job_id = job_list[i].find('a', {'class': 'base-card'}).get('data-entity-urn').split(':')[3]
                job_ids.append(job_id)
            except Exception as e:
                log_error(e)
                log_info(job_list[i])
    return job_ids


def job_detail(job_id):
    uri = POST_URL + job_id
    res = requests.get(uri, headers=HEADERS)

    if not res.ok or len(res.history) > 0:
        return job_detail(job_id)

    soup = BeautifulSoup(res.text, 'html.parser')

    detail = {
        'title': None,
        'company': None,
        'location': None,
        'id': job_id,
        'link': uri,
        'description': None,
        'time': None,
        'level': None,
        'industry': None,
        'type': None,
        'function': None,
    }

    try:
        anchor_element = soup.find("div",{"class":"top-card-layout__entity-info"}).find("a")

        detail['link'] = anchor_element.get('href')
        detail['title'] = anchor_element.text.strip()
    except Exception as e:
        log_error(e)
        log_info(f"cannot fetch job title for {job_id}")
        log_info(soup)

    try:
        detail['company'] = soup.find('a', {'class': 'topcard__org-name-link'}).text.strip()
    except:
        try:
            detail['company'] = soup.select_one('.topcard__flavor-row > span.topcard__flavor').text.strip()
        except Exception as e:
            log_error(e)
            log_info(f"cannot fetch job company for {job_id}")
            log_info(soup)

    try:
        detail['location'] = soup.select_one('h4.top-card-layout__second-subline > div.topcard__flavor-row > span.topcard__flavor.topcard__flavor--bullet').text.strip()
    except Exception as e:
        log_error(e)
        log_info(f"cannot fetch job company for {job_id}")
        log_info(soup)

    try:
        detail['time'] = soup.select_one('.posted-time-ago__text').text.strip()
    except Exception as e:
        log_error(e)
        log_info(f"cannot fetch job time for {job_id}")
        log_info(soup)

    try:
        detail['description'] = soup.select_one('.show-more-less-html__markup.show-more-less-html__markup--clamp-after-5').text.strip()
    except Exception as e:
        log_error(e)
        log_info(f"cannot fetch job description for {job_id}")
        log_info(soup)

    try:
        keys = {
            'Tingkat senioritas': 'level',
            'Seniority level': 'level',
            'Fungsi pekerjaan': 'function',
            'Job function': 'function',
            'Jenis pekerjaan': 'type',
            'Employment type': 'type',
            'Industri': 'industry',
            'Industries': 'industry',
        }
        criterias = soup.select('li.description__job-criteria-item')
        for i in range(0, len(criterias)):
            key = criterias[i].select_one('.description__job-criteria-subheader').text.strip()
            detail[keys[key]] = criterias[i].select_one('.description__job-criteria-text').text.strip()
    except Exception as e:
        log_error(e)
        log_info(f"cannot fetch job criterias for {job_id}")
        log_info(soup)

    return detail


def main():
    job_ids = []
    job_list = []
    
    try:
        total = job_result()
        num_page = math.ceil(total/25)
        print(f"{total} {'jobs' if total > 1 else 'job'} available within {num_page} {'pages' if num_page > 1 else 'page'}")

        for i in tqdm(range(0, num_page), desc='Page'):
            start = (i+1)*25
            job_ids += job_id_list_per_page(start)

        for i in tqdm(range(0, len(job_ids)), desc='Jobs'):
            job_list.append(job_detail(job_ids[i]))

        df = pd.DataFrame(job_list)
        df.to_csv('out.csv', index=False, encoding='utf-8')
        
        print('Successfully exported available job(s) to out.csv')
    except Exception as e:
        log_error(e)
        print(f"Fatal error, please check log.txt")


if __name__ == "__main__":
    main()