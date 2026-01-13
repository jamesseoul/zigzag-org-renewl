from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse
import re
import os

app = Flask(__name__)
CORS(app)  # CORS 문제 해결

@app.route('/')
def index():
    """메인 페이지 제공"""
    return send_file('index.html')

@app.route('/api/extract', methods=['POST'])
def extract_product():
    try:
        data = request.get_json()
        url = data.get('url')

        if not url:
            return jsonify({'error': '유효한 URL을 입력해주세요'}), 400

        # URL에서 정보 추출
        domain = urlparse(url).netloc.replace('www.', '')

        # User-Agent 헤더 추가 (일부 사이트는 봇 차단)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # 페이지 가져오기
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # HTML 파싱
        soup = BeautifulSoup(response.content, 'html.parser')

        # 도메인별 상품 정보 추출
        product_info = extract_by_domain(soup, domain, url)

        return jsonify(product_info)

    except requests.exceptions.Timeout:
        return jsonify({'error': '요청 시간이 초과되었습니다'}), 408
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'페이지를 가져올 수 없습니다: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'오류가 발생했습니다: {str(e)}'}), 500


def extract_by_domain(soup, domain, url):
    """도메인별로 상품 정보 추출"""

    # 기본 정보 (Open Graph 태그에서 추출)
    title = extract_meta_tag(soup, 'og:title') or extract_meta_tag(soup, 'twitter:title') or soup.find('title')
    if title and hasattr(title, 'text'):
        title = title.text
    title = str(title) if title else '제목 없음'

    description = extract_meta_tag(soup, 'og:description') or extract_meta_tag(soup, 'description')
    description = str(description) if description else '설명 없음'

    image = extract_meta_tag(soup, 'og:image') or extract_meta_tag(soup, 'twitter:image')

    # 가격 추출 시도
    price = extract_price(soup)

    # 도메인 정보
    seller_map = {
        'coupang.com': '쿠팡',
        'naver.com': '네이버 쇼핑',
        'gmarket.co.kr': 'G마켓',
        '11st.co.kr': '11번가',
        'amazon.com': 'Amazon',
        'aliexpress.com': 'AliExpress',
    }

    seller = seller_map.get(domain, domain)

    return {
        'title': clean_text(title),
        'price': price or '가격 정보 없음',
        'seller': seller,
        'category': '분류 정보 없음',
        'rating': '평점 정보 없음',
        'description': clean_text(description)[:300],  # 설명은 300자로 제한
        'image': image,
        'url': url
    }


def extract_meta_tag(soup, property_name):
    """메타 태그에서 정보 추출"""
    tag = soup.find('meta', property=property_name) or soup.find('meta', attrs={'name': property_name})
    if tag and tag.get('content'):
        return tag.get('content')
    return None


def extract_price(soup):
    """가격 정보 추출"""
    # 일반적인 가격 패턴들
    price_patterns = [
        r'[\₩$€£¥]\s*[\d,]+',
        r'[\d,]+\s*원',
        r'[\d,]+\s*[원|won]',
    ]

    # 가격 관련 클래스/ID 찾기
    price_elements = soup.find_all(class_=re.compile(r'price', re.I))
    price_elements += soup.find_all(id=re.compile(r'price', re.I))

    for element in price_elements:
        text = element.get_text()
        for pattern in price_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)

    # 전체 HTML에서 가격 패턴 찾기 (최후의 수단)
    text = soup.get_text()
    for pattern in price_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)

    return None


def clean_text(text):
    """텍스트 정리"""
    if not text:
        return ''
    # 여러 공백을 하나로
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    print("🚀 서버가 http://localhost:5000 에서 실행됩니다")
    print("📝 프론트엔드에서 http://localhost:5000/api/extract 로 요청하세요")
    app.run(debug=True, host='0.0.0.0', port=5000)
