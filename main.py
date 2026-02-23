#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
이미지 썸네일 생성기 (최신 버전)
- 이미지 URL로부터 이미지를 다운로드하고 처리
- 정방형 크롭, 어두운 필터, 테두리, 텍스트 삽입
- 외부 서버 업로드 및 URL 반환
- 줄간격 1.3 적용으로 최적화된 텍스트 레이아웃
"""

import requests
import io
import os
import random
import uuid
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import sys
import threading
import http.server
import socketserver
from urllib.parse import quote
import webbrowser
import json
import argparse
import time

class ThumbnailGenerator:
    def __init__(self):
        """썸네일 생성기 초기화"""
        self.target_size = (1080, 1080)  # 최종 이미지 크기
        self.border_margin = 60  # 테두리 여백 (px)
        self.border_width = 8    # 테두리 두께 (px)
        self.overlay_opacity = 0.43  # 어두운 필터 불투명도 (43%)
        self.default_font_size = 180  # 기본 폰트 크기 (pt) - 대형 폰트
        self.line_spacing = 1.3  # 줄간격 비율 (1.0이 기본 줄간격, 값이 클수록 줄간격이 넓어짐)
        self.upload_url = "http://localhost:9999/upload"  # 로컬 Docker 파일서버 URL
        
        # 한글 폰트 경로 목록 (페이퍼로지 폰트 우선)
        self.font_paths = [
            os.path.join(os.path.dirname(__file__), "fonts", "Paperlogy-7Bold.ttf"),    # 프로그램 폴더 내 fonts
            os.path.join(os.path.dirname(__file__), "Paperlogy-7Bold.ttf"),             # 프로그램 폴더 루트
            "Paperlogy-7Bold.ttf",                                                      # 현재 작업 디렉토리
            "C:/Windows/Fonts/Paperlogy-7Bold.ttf",                                     # Windows 폰트 폴더
            "C:/Windows/Fonts/malgun.ttf",                                              # 맑은 고딕
            "C:/Windows/Fonts/malgunbd.ttf",                                            # 맑은 고딕 볼드
            "C:/Windows/Fonts/gulim.ttc",                                               # 굴림
            "C:/Windows/Fonts/batang.ttc",                                              # 바탕
            "C:/Windows/Fonts/NanumGothic.ttf",                                         # 나눔고딕 (설치된 경우)
            "C:/Windows/Fonts/arial.ttf",                                               # Arial (fallback)
        ]
        
        # 웹서버 관련 설정
        self.local_port = 8000
        self.server_thread = None
        self.httpd = None

    def download_image(self, image_url):
        """
        이미지 URL로부터 이미지를 다운로드
        
        Args:
            image_url (str): 다운로드할 이미지의 URL
            
        Returns:
            PIL.Image: 다운로드된 이미지 객체
            
        Raises:
            requests.RequestException: 네트워크 오류
            IOError: 이미지 파일 오류
        """
        try:
            print(f"이미지 다운로드 중: {image_url}")
            
            # HTTP 헤더 설정 (일부 사이트에서 User-Agent 필요)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # 이미지 다운로드 (타임아웃 30초)
            response = requests.get(image_url, headers=headers, timeout=30)
            response.raise_for_status()  # HTTP 오류 발생시 예외 처리
            
            # 바이트 스트림으로부터 이미지 로드
            image_bytes = io.BytesIO(response.content)
            image = Image.open(image_bytes)
            
            # RGB 모드로 변환 (RGBA, P 모드 등을 RGB로 통일)
            if image.mode != 'RGB':
                image = image.convert('RGB')
                
            print(f"이미지 다운로드 완료: {image.size}")
            return image
            
        except requests.RequestException as e:
            raise Exception(f"네트워크 오류: 이미지를 다운로드할 수 없습니다. {str(e)}")
        except IOError as e:
            raise Exception(f"이미지 파일 오류: 올바른 이미지 형식이 아닙니다. {str(e)}")

    def crop_to_square(self, image):
        """
        이미지를 정방형으로 크롭 (중심 기준, 짧은 축 기준)
        
        Args:
            image (PIL.Image): 원본 이미지
            
        Returns:
            PIL.Image: 정방형으로 크롭된 이미지
        """
        width, height = image.size
        
        # 짧은 축을 기준으로 정방형 크기 결정
        crop_size = min(width, height)
        
        # 중심점 계산
        left = (width - crop_size) // 2
        top = (height - crop_size) // 2
        right = left + crop_size
        bottom = top + crop_size
        
        # 크롭 실행
        cropped_image = image.crop((left, top, right, bottom))
        print(f"정방형 크롭 완료: {cropped_image.size}")
        
        return cropped_image

    def resize_image(self, image, target_size):
        """
        이미지를 지정된 크기로 리사이징
        
        Args:
            image (PIL.Image): 원본 이미지
            target_size (tuple): 목표 크기 (width, height)
            
        Returns:
            PIL.Image: 리사이징된 이미지
        """
        resized_image = image.resize(target_size, Image.Resampling.LANCZOS)
        print(f"리사이징 완료: {resized_image.size}")
        return resized_image

    def apply_dark_overlay(self, image, opacity=0.43):
        """
        이미지에 어두운 반투명 레이어 적용
        
        Args:
            image (PIL.Image): 원본 이미지
            opacity (float): 불투명도 (0.0~1.0)
            
        Returns:
            PIL.Image: 어두운 필터가 적용된 이미지
        """
        # 검은색 오버레이 레이어 생성
        overlay = Image.new('RGBA', image.size, (0, 0, 0, int(255 * opacity)))
        
        # 원본 이미지를 RGBA로 변환
        base_image = image.convert('RGBA')
        
        # 오버레이 합성
        darkened_image = Image.alpha_composite(base_image, overlay)
        
        # RGB로 다시 변환
        darkened_image = darkened_image.convert('RGB')
        
        print(f"어두운 필터 적용 완료 (불투명도: {opacity*100:.0f}%)")
        return darkened_image

    def add_border(self, image, margin=60, border_width=8):
        """
        이미지에 흰색 테두리 추가
        
        Args:
            image (PIL.Image): 원본 이미지
            margin (int): 가장자리로부터의 여백 (px)
            border_width (int): 테두리 두께 (px)
            
        Returns:
            PIL.Image: 테두리가 추가된 이미지
        """
        draw = ImageDraw.Draw(image)
        width, height = image.size
        
        # 테두리 좌표 계산
        x1 = margin
        y1 = margin
        x2 = width - margin
        y2 = height - margin
        
        # 흰색 테두리 그리기 (여러번 그려서 두께 구현)
        for i in range(border_width):
            draw.rectangle([x1-i, y1-i, x2+i, y2+i], outline='white', width=1)
        
        print(f"테두리 추가 완료 (여백: {margin}px, 두께: {border_width}px)")
        return image

    def load_font(self, font_size):
        """
        한글 폰트 로드 (볼드체 우선)
        
        Args:
            font_size (int): 폰트 크기
            
        Returns:
            PIL.ImageFont: 로드된 폰트 객체
        """
        for font_path in self.font_paths:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    print(f"폰트 로드 성공: {font_path}")
                    return font
                except IOError:
                    continue
        
        # 모든 폰트 로드 실패시 기본 폰트 사용
        print("경고: 지정된 폰트를 찾을 수 없어 기본 폰트를 사용합니다.")
        return ImageFont.load_default()

    def wrap_text(self, text, font, max_width):
        """
        텍스트를 지정된 너비에 맞춰 줄바꿈 처리
        
        Args:
            text (str): 원본 텍스트
            font (PIL.ImageFont): 폰트 객체
            max_width (int): 최대 너비
            
        Returns:
            list: 줄바꿈된 텍스트 라인 리스트
        """
        words = text.split(' ')
        lines = []
        current_line = ""
        
        for word in words:
            # 현재 줄에 단어를 추가했을 때의 너비 계산
            test_line = current_line + (" " if current_line else "") + word
            test_width = self.get_text_width(test_line, font)
            
            if test_width <= max_width:
                current_line = test_line
            else:
                # 현재 줄이 비어있지 않으면 라인에 추가
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        # 마지막 줄 추가
        if current_line:
            lines.append(current_line)
        
        return lines

    def get_text_width(self, text, font):
        """
        텍스트 너비 계산
        
        Args:
            text (str): 텍스트
            font (PIL.ImageFont): 폰트 객체
            
        Returns:
            int: 텍스트 너비
        """
        temp_img = Image.new('RGB', (1, 1))
        temp_draw = ImageDraw.Draw(temp_img)
        bbox = temp_draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]

    def get_text_height(self, text, font):
        """
        텍스트 높이 계산
        
        Args:
            text (str): 텍스트
            font (PIL.ImageFont): 폰트 객체
            
        Returns:
            int: 텍스트 높이
        """
        temp_img = Image.new('RGB', (1, 1))
        temp_draw = ImageDraw.Draw(temp_img)
        bbox = temp_draw.textbbox((0, 0), text, font=font)
        return bbox[3] - bbox[1]

    def calculate_multiline_text_size(self, lines, font, line_spacing=1.2):
        """
        다중 라인 텍스트의 전체 크기 계산
        
        Args:
            lines (list): 텍스트 라인 리스트
            font (PIL.ImageFont): 폰트 객체
            line_spacing (float): 줄 간격 비율
            
        Returns:
            tuple: (전체 너비, 전체 높이)
        """
        if not lines:
            return 0, 0
        
        max_width = 0
        line_height = self.get_text_height(lines[0], font)
        total_height = line_height * len(lines)
        
        # 줄 간격 추가 (마지막 줄 제외)
        if len(lines) > 1:
            total_height += line_height * (line_spacing - 1) * (len(lines) - 1)
        
        # 가장 긴 줄의 너비 찾기
        for line in lines:
            width = self.get_text_width(line, font)
            max_width = max(max_width, width)
        
        return max_width, int(total_height)
    def calculate_text_size(self, text, font):
        """
        텍스트의 실제 크기 계산 (단일 라인용)
        
        Args:
            text (str): 측정할 텍스트
            font (PIL.ImageFont): 폰트 객체
            
        Returns:
            tuple: (width, height) 텍스트 크기
        """
        # 임시 이미지에서 텍스트 크기 측정
        temp_img = Image.new('RGB', (1, 1))
        temp_draw = ImageDraw.Draw(temp_img)
        bbox = temp_draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    def add_text_overlay(self, image, title_text):
        """
        이미지 중앙에 제목 텍스트 추가 (대형 다중 라인 지원)
        
        Args:
            image (PIL.Image): 원본 이미지
            title_text (str): 추가할 제목 텍스트
            
        Returns:
            PIL.Image: 텍스트가 추가된 이미지
        """
        draw = ImageDraw.Draw(image)
        width, height = image.size
        
        # 텍스트 영역 계산 (테두리 안쪽, 더 넓은 영역 사용)
        margin = self.border_margin + self.border_width + 30  # 여백을 30px로 설정
        text_area_width = width - 2 * margin
        text_area_height = height - 2 * margin
        
        print(f"텍스트 영역: {text_area_width} x {text_area_height}")
        
        # 폰트 크기 자동 조정 (더 크게 시작)
        font_size = self.default_font_size
        min_font_size = 40  # 최소 폰트 크기 증가
        line_spacing = self.line_spacing  # 클래스에서 설정한 줄 간격 사용
        
        while font_size >= min_font_size:
            font = self.load_font(font_size)
            
            # 텍스트를 줄바꿈 처리
            lines = self.wrap_text(title_text, font, text_area_width)
            
            # 전체 텍스트 크기 계산
            total_width, total_height = self.calculate_multiline_text_size(lines, font, line_spacing)
            
            print(f"폰트 {font_size}pt 테스트: {len(lines)}줄, {total_width}x{total_height}")
            
            # 영역에 맞는지 확인
            if total_width <= text_area_width and total_height <= text_area_height:
                break
                
            # 폰트 크기 감소
            font_size -= 10  # 더 크게 감소
        
        # 최종 폰트 및 줄바꿈 적용
        font = self.load_font(font_size)
        lines = self.wrap_text(title_text, font, text_area_width)
        
        # 전체 텍스트 크기 재계산
        total_width, total_height = self.calculate_multiline_text_size(lines, font, line_spacing)
        
        # 전체 영역에서 중앙 정렬을 위한 시작 위치 계산
        start_x = (width - total_width) // 2
        start_y = (height - total_height) // 2
        
        # 각 라인 그리기
        line_height = self.get_text_height(lines[0] if lines else "A", font)
        current_y = start_y
        
        for i, line in enumerate(lines):
            # 각 라인의 너비 계산 및 중앙 정렬
            line_width = self.get_text_width(line, font)
            line_x = (width - line_width) // 2
            
            # 텍스트 그리기 (흰색)
            draw.text((line_x, current_y), line, fill='white', font=font)
            
            # 다음 줄로 이동
            if i < len(lines) - 1:  # 마지막 줄이 아니면
                current_y += int(line_height * line_spacing)
        
        print(f"대형 텍스트 추가 완료: '{title_text}' ({len(lines)}줄, 폰트 크기: {font_size}pt)")
        return image

    def generate_filename(self):
        """
        중복되지 않는 랜덤 파일명 생성
        
        Returns:
            str: 생성된 파일명
        """
        # UUID와 랜덤 숫자를 조합하여 중복 방지
        random_uuid = str(uuid.uuid4())[:8]
        random_num = random.randint(1000, 9999)
        filename = f"output_thumbnail_{random_uuid}_{random_num}.png"
        return filename

    def upload_to_server(self, image, filename):
        """
        이미지를 외부 서버에 업로드
        
        Args:
            image (PIL.Image): 업로드할 이미지
            filename (str): 파일명
            
        Returns:
            str: 업로드된 이미지의 URL
        """
        try:
            print(f"외부 서버 업로드 시작: {filename}")
            
            # 이미지를 바이트 스트림으로 변환
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG', optimize=True)
            img_byte_arr.seek(0)
            
            # 업로드 요청
            files = {'file': (filename, img_byte_arr, 'image/png')}
            external_upload_url = "https://files.goseecloud.com/upload"
            
            print(f"업로드 URL: {external_upload_url}")
            response = requests.post(external_upload_url, files=files, timeout=60)
            
            print(f"서버 응답 상태 코드: {response.status_code}")
            print(f"서버 응답 내용: {response.text[:500]}...")  # 처음 500자만 출력
            
            response.raise_for_status()
            
            # 응답에서 업로드된 파일 URL 추출
            try:
                result = response.json()
                print(f"서버 JSON 응답: {result}")
                
                if 'download_url' in result:
                    # 상대 경로를 절대 URL로 변환
                    uploaded_url = f"https://files.goseecloud.com{result['download_url']}"
                elif 'view_url' in result:
                    uploaded_url = f"https://files.goseecloud.com{result['view_url']}"
                elif 'url' in result:
                    uploaded_url = result['url']
                elif 'file_url' in result:
                    uploaded_url = result['file_url']
                else:
                    # JSON 응답이 있지만 URL 키를 찾지 못한 경우
                    print("경고: 서버 응답에서 URL을 찾을 수 없습니다. 기본 URL을 사용합니다.")
                    uploaded_url = f"https://files.goseecloud.com/{filename}"
                    
            except ValueError as e:
                print(f"JSON 파싱 실패: {e}")
                print("텍스트 응답을 URL로 사용 시도...")
                
                # JSON이 아닌 경우 응답 텍스트가 URL일 가능성 확인
                response_text = response.text.strip()
                if response_text.startswith('http'):
                    uploaded_url = response_text
                else:
                    uploaded_url = f"https://files.goseecloud.com/{filename}"
            
            print(f"업로드 완료: {uploaded_url}")
            return uploaded_url
            
        except requests.RequestException as e:
            print(f"외부 서버 업로드 실패: {str(e)}")
            raise Exception(f"업로드 실패: {str(e)}")

    def upload_to_external_server_with_url(self, image_url, title_text):
        """
        이미지 URL로부터 썸네일을 생성하고 외부 서버에 업로드
        
        Args:
            image_url (str): 이미지 URL
            title_text (str): 제목 텍스트
            
        Returns:
            dict: JSON 응답
        """
        try:
            print(f"🌍 이미지 URL로부터 썸네일 생성 시작: {image_url}")
            
            # 1. 이미지 다운로드
            image = self.download_image(image_url)
            
            # 2. 정방형 크롭
            image = self.crop_to_square(image)
            
            # 3. 1080x1080 리사이징
            image = self.resize_image(image, self.target_size)
            
            # 4. 어두운 필터 적용
            image = self.apply_dark_overlay(image, self.overlay_opacity)
            
            # 5. 테두리 추가
            image = self.add_border(image, self.border_margin, self.border_width)
            
            # 6. 텍스트 추가
            image = self.add_text_overlay(image, title_text)
            
            # 7. 파일명 생성
            filename = self.generate_filename()
            
            # 8. 외부 서버에 업로드
            uploaded_url = self.upload_to_server(image, filename)
            
            return {
                "success": True,
                "message": "썸네일이 성공적으로 생성되었습니다.",
                "url": uploaded_url,
                "filename": filename,
                "source_image": image_url,
                "title": title_text
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": "썸네일 생성 중 오류가 발생했습니다.",
                "error": str(e)
            }

    def start_local_server(self):
        """
        로컬 웹서버 시작 (output 폴더 서빙)
        
        Returns:
            int: 웹서버가 실행중인 포트 번호
        """
        try:
            output_dir = os.path.join(os.getcwd(), "output")
            os.makedirs(output_dir, exist_ok=True)
            
            # 사용 가능한 포트 찾기
            for port in range(8000, 8100):
                try:
                    os.chdir(output_dir)
                    handler = http.server.SimpleHTTPRequestHandler
                    self.httpd = socketserver.TCPServer(("", port), handler)
                    self.local_port = port
                    break
                except OSError:
                    continue
            else:
                raise Exception("사용 가능한 포트를 찾을 수 없습니다.")
            
            # 백그라운드에서 서버 실행
            def run_server():
                print(f"로컬 웹서버 시작: http://localhost:{self.local_port}")
                self.httpd.serve_forever()
            
            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            
            # 원래 디렉토리로 돌아가기
            os.chdir(os.path.dirname(output_dir))
            
            return self.local_port
            
        except Exception as e:
            print(f"로컬 서버 시작 실패: {str(e)}")
            return None

    def stop_local_server(self):
        """
        로컬 웹서버 종료
        """
        if self.httpd:
            self.httpd.shutdown()
            print("로컬 웹서버가 종료되었습니다.")

    def process_image(self, image_url, title_text, use_localhost=True, use_docker=False, use_external=False):
        """
        전체 이미지 처리 프로세스 실행
        
        Args:
            image_url (str): 처리할 이미지 URL
            title_text (str): 추가할 제목 텍스트
            use_localhost (bool): 로컬호스트 웹서버 사용 여부
            use_docker (bool): 로컬 Docker 파일서버 사용 여부
            use_external (bool): 외부 서버 업로드 사용 여부
            
        Returns:
            tuple: (결과 URL, 로컬 파일 경로)
        """
        try:
            # 1. 이미지 다운로드
            image = self.download_image(image_url)
            
            # 2. 정방형 크롭
            image = self.crop_to_square(image)
            
            # 3. 1080x1080 리사이징
            image = self.resize_image(image, self.target_size)
            
            # 4. 어두운 필터 적용
            image = self.apply_dark_overlay(image, self.overlay_opacity)
            
            # 5. 테두리 추가
            image = self.add_border(image, self.border_margin, self.border_width)
            
            # 6. 텍스트 추가
            image = self.add_text_overlay(image, title_text)
            
            # 7. 파일명 생성
            filename = self.generate_filename()
            
            # 8. URL 결정
            if use_localhost:
                print("로컬호스트 모드는 더 이상 지원되지 않습니다.")
                raise Exception("로컬호스트 모드는 더 이상 지원되지 않습니다.")
            elif use_external:
                # 외부 서버에 업로드
                try:
                    uploaded_url = self.upload_to_server(image, filename)
                    return uploaded_url, uploaded_url
                except Exception as e:
                    print(f"외부 서버 업로드 실패: {e}")
                    print(f"로컬 파일을 대신 사용합니다: {local_path}")
                    return local_path, local_path
            else:
                return local_path, local_path
            
        except Exception as e:
            print(f"오류 발생: {str(e)}")
            raise

# 간단한 테스트 함수
if __name__ == "__main__":
    print("🔧 썸네일 생성기 테스트")
    generator = ThumbnailGenerator()
    
    try:
        result_url, local_path = generator.process_image(
            "https://picsum.photos/800/600",
            "페이퍼로지 대형 텍스트",
            use_localhost=False,
            use_external=True
        )
        
        print(f"\n✅ 생성 완료!")
        print(f"URL: {result_url}")
        print(f"파일: {local_path}")
        
        input("아무 키나 누르면 종료합니다...")
        
    except Exception as e:
        print(f"❌ 오류: {e}")
    finally:
        if generator.httpd:
            generator.stop_local_server()