#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
줄간격 테스트 스크립트
"""

import os
import sys
from main import ThumbnailGenerator

def test_line_spacing(line_spacing_value, output_suffix):
    """줄간격 테스트 함수"""
    print(f"\n=== 줄간격 {line_spacing_value} 테스트 ===")
    
    try:
        # ThumbnailGenerator 인스턴스 생성
        generator = ThumbnailGenerator()
        
        # 줄간격 설정 변경
        generator.line_spacing = line_spacing_value
        print(f"줄간격 설정: {generator.line_spacing}")
        
        # 테스트 이미지 URL (픽섬)
        test_image_url = "https://picsum.photos/800/600"
        test_title = "치과보험 임플란트 총정리"
        
        print(f"제목: {test_title}")
        print(f"이미지 URL: {test_image_url}")
        
        # 이미지 다운로드
        image = generator.download_image(test_image_url)
        
        # 정방형 크롭
        image = generator.crop_to_square(image)
        
        # 리사이징
        image = generator.resize_image(image, generator.target_size)
        
        # 어두운 필터 적용
        image = generator.apply_dark_overlay(image, generator.overlay_opacity)
        
        # 테두리 추가
        image = generator.add_border(image, generator.border_margin, generator.border_width)
        
        # 텍스트 추가
        image = generator.add_text_overlay(image, test_title)
        
        # output 폴더 생성
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        
        # 파일 저장
        output_filename = f"test_line_spacing_{output_suffix}.png"
        output_path = os.path.join(output_dir, output_filename)
        image.save(output_path, "PNG")
        
        print(f"✅ 테스트 완료: {output_path}")
        
        return output_path
        
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        return None

if __name__ == "__main__":
    print("🔧 줄간격 비교 테스트 시작")
    
    # 1.5 줄간격 테스트
    result_1_5 = test_line_spacing(1.5, "1_5")
    
    # 2.0 줄간격 테스트
    result_2_0 = test_line_spacing(2.0, "2_0")
    
    print("\n📋 테스트 결과:")
    print(f"줄간격 1.5: {result_1_5}")
    print(f"줄간격 2.0: {result_2_0}")
    
    if result_1_5 and result_2_0:
        print("\n✅ 모든 테스트 완료!")
        print("output 폴더에서 두 이미지를 비교해보세요.")
    else:
        print("\n❌ 일부 테스트 실패")