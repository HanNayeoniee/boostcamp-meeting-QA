import json
import pprint
import warnings
import re
import os
import argparse
from tqdm import tqdm
from elasticsearch import Elasticsearch

warnings.filterwarnings('ignore')

"""
Elasticsearch를 사용하기 전 처음에 한 번 실행시켜주세요!!!
데이터 index 설정값을 바꾸거나 새로운 데이터를 삽입할 때는 index_name을 변경해서 실행시켜주세요!!!
"""

def es_setting(index_name="origin-meeting-wiki"):
    """
    elasticsearch 서버 세팅 
    """
    es = Elasticsearch('http://localhost:9200', timeout=30, max_retries=10, retry_on_timeout=True)
    print("Ping Elasticsearch :", es.ping())
    print('Elastic search info:')
    print(es.info())

    return es, index_name

def create_index(es, index_name, setting_path):
    """
    인덱스 생성
    """
    with open(setting_path, "r") as f:
        setting = json.load(f)
    es.indices.create(index=index_name, body=setting)
    print("Index creation has been completed")

def delete_index(es, index_name):
    """
    인덱스 삭제
    """
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
        print("Deleting index {} ...".format(index_name))
    else:
        print("Index {} does not exist.".format(index_name))

def delete_doc(es, index_name, doc_id):
    """
    문서 id로 인덱스에서 문서 삭제 후 삭제한 문서 반환
    """
    if es.exists(index=index_name, id=doc_id):
        es.delete(index=index_name, id=doc_id)
        print("Deleting id {} from index {} ...".format(doc_id, index_name))
    else:
        print("Id {} does not existin index {}.".format(doc_id, index_name))

    deleted_doc = es.get(index=index_name, id=doc_id)

    return deleted_doc['_source']['document_text']

def initial_index(es, index_name, setting_path):
    """
    처음에 인덱스를 초기화하고 생성하는 경우
    """
    delete_index(es, index_name)
    create_index(es, index_name, setting_path)

def preprocess(text):
    """
    삽입할 데이터 전처리
    """
    text = re.sub(r"\n", " ", text)
    text = re.sub(r"\\n", " ", text)
    text = re.sub(r"#", " ", text)
    text = re.sub(r"[^A-Za-z0-9가-힣.?!,()~‘’“”"":%&《》〈〉''㈜·\-\'+\s一-龥]", "", text)
    text = re.sub(r"\s+", " ", text).strip()  # 두 개 이상의 연속된 공백을 하나로 치환
    
    return text

def load_json(dataset_path):
    """
    json형식의 위키피디아 데이터 로드
    """
    # dataset_path = "../data/meeting_collection.json"
    with open(dataset_path, "r") as f:
        wiki = json.load(f)

    texts = list(dict.fromkeys([v["text"] for v in wiki.values()]))
    texts = [preprocess(text) for text in texts]
    corpus = [
        {"document_text": texts[i]} for i in range(len(texts))
    ]
    return corpus

def load_txt(folder):
    """
    사용자가 추가한 폴더의 모든 txt파일 로드
    """
    # folder = "../data/new_data/"
    file_list = os.listdir(folder)
    file_list_txt = [file for file in file_list if file.endswith(".txt")]

    texts = []
    for file in file_list_txt:
        path = os.path.join(folder, file)
        f = open(path, "r")
        data = f.read()
        f.close()
        texts.append(data)

    texts = [preprocess(text) for text in texts]
    corpus = [
        {"document_text": texts[i]} for i in range(len(texts))
    ]
    
    return corpus

def insert_data(es, index_name, dataset_path, type="json", start_id=None):
    """
    인덱스에 데이터 삽입
    type에는 "json", "txt" 가능
    """
    if type == "json":
        corpus = load_json(dataset_path)
    elif type == "txt":
        corpus = load_txt(dataset_path)

    for i, text in enumerate(tqdm(corpus)):
        try:
            if isinstance(start_id, int):
                es.index(index=index_name, id=start_id+i, body=text)    
            else:
                es.index(index=index_name, id=i, body=text)
        except:
            print(f"Unable to load document {i}.")

    n_records = count_doc(es, index_name=index_name)
    print(f"Succesfully loaded {n_records} into {index_name}")
    print("@@@@@@@ 데이터 삽입 완료 @@@@@@@")

def update_doc(es, index_name, doc_id, data_path):
    f = open(data_path, "r")  # 수정할 텍스트
    text = f.read()
    new_text = {"document_text" : text}
    es.update(es, index=index_name, id=doc_id, doc=new_text)
    
    print(f"Succesfully updated doc {doc_id} in {index_name}")
    print("@@@@@@@ 문서 수정 완료 @@@@@@@")

def count_doc(es, index_name):
    """
    특정 인덱스의 문서 개수 세기
    """
    n_records = es.count(index=index_name)["count"]
    return n_records

def check_data(es, index_name, doc_id=0):
    """
    삽입한 데이터 확인
    """
    print('샘플 데이터:')
    doc = es.get(index=index_name, id=doc_id)
    pprint.pprint(doc)

def es_search(es, index_name, question, topk):
    # question = "대통령을 포함한 미국의 행정부 견제권을 갖는 국가 기관은?"
    query = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"document_text": question}}
                ]
            }
        }
    }

    res = es.search(index=index_name, body=query, size=topk)
    return res

def search_all(es, index_name):
    """
    인덱스 내 모든 문서 반환
    """
    query = {
        "query": {
            "match_all": {}
        }
    }

    res = es.search(index=index_name, body=query)
    return res
    

def main1(args):
    """
    사용자가 처음 회의록을 삽입하는 경우
    """
    es, index_name = es_setting(index_name=args.index_name)
    initial_index(es, index_name, args.setting_path)
    insert_data(es, index_name, args.dataset_path, type="json")


    query = "제154회 완주군의회 임시회 제2차 본회의에서 5분 발언을 한 사람은 누구야?"
    res = es_search(es, index_name, query, 10)
    print("========== RETRIEVE RESULTS ==========")
    pprint.pprint(res)

    print('\n=========== RETRIEVE SCORES ==========\n')
    for hit in res['hits']['hits']:
        print("Doc ID: %3r  Score: %5.2f" % (hit['_id'], hit['_score']))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("--setting_path", default="./setting.json", type=str, help="생성할 index의 setting.json 경로를 설정해주세요")
    parser.add_argument("--dataset_path", default="../data/meeting_collection.json", type=str, help="삽입할 데이터의 경로를 설정해주세요")
    parser.add_argument("--index_name", default="origin-meeting-wiki", type=str, help="테스트할 index name을 설정해주세요")

    args = parser.parse_args()
    main1(args)
    print("main1 완료")


def main2(args):
    """
    미리 인덱스 생성 후, 사용자가 회의록을 추가 삽입하는 경우
    """
    es, index_name = es_setting(index_name=args.index_name)
    doc_num = count_doc(es, index_name)
    insert_data(es, index_name, args.dataset_path, type="txt", start_id=doc_num)
    check_data(es, index_name, doc_id=1)

    query = "제154회 완주군의회 임시회 제2차 본회의에서 5분 발언을 한 사람은 누구야?"
    res = es_search(es, index_name, query, 10)
    print("========== RETRIEVE RESULTS ==========")
    pprint.pprint(res)

    print('\n=========== RETRIEVE SCORES ==========\n')
    for hit in res['hits']['hits']:
        print("Doc ID: %3r  Score: %5.2f" % (hit['_id'], hit['_score']))

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description="")
#     parser.add_argument("--setting_path", default="./setting.json", type=str, help="생성할 index의 setting.json 경로를 설정해주세요")
#     parser.add_argument("--dataset_path", default="../data/new_data/", type=str, help="삽입할 데이터의 경로를 설정해주세요")
#     parser.add_argument("--index_name", default="sample2", type=str, help="테스트할 index name을 설정해주세요")

#     args = parser.parse_args()
#     main2(args)