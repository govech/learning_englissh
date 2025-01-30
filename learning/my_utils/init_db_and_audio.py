import logging
import os
import random
import time

from django.conf import settings

from django.core.files.storage import default_storage
from django.db import transaction

import requests
from lxml import html

from learning.models import Word, AudioFile

# Create your views here.

# 设置日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

"""
此脚本用于为单词下载音标、发音、翻译
"""


def word_card():
    start_time = time.time()

    try:
        # 获取所有在 Word 表中但不在 AudioFile 表中的数据的 ID 列表
        word_ids = list(Word.objects.exclude(
            word__in=AudioFile.objects.values('word_text')
        ).values_list('id', flat=True))

        if not word_ids:
            logging.warning("No words found in Word table that are not in AudioFile table.")
            return ""

        # 随机选择一个 ID
        # random_word_id = random.choice(word_ids)
        random_word_id = word_ids[0]
        random_word = Word.objects.get(id=random_word_id)
        logging.info(f"Selected word is: {random_word}")
        # 初始化变量
        phonetic = ""
        uk_pronunciation_link = ""
        us_pronunciation_link = ""

        # 如果单词没有中文意思，调用翻译 API 获取并保存
        if not random_word.definition or not random_word.phonetic_uk or not random_word.phonetic_us:
            try:
                phonetic, chinese_meaning, uk_pronunciation_link, us_pronunciation_link = get_youdao_data(random_word)
                if chinese_meaning:
                    with transaction.atomic():
                        random_word.definition = chinese_meaning
                        random_word.phonetic = phonetic
                        random_word.save()
            except Exception as e:
                logging.error(f"Failed to get Youdao data: {e}")

        if not random_word.phonetic_uk and uk_pronunciation_link:
            try:
                download_and_save_audio(uk_pronunciation_link, random_word, "uk")
            except Exception as e:
                logging.error(f"Failed to download UK pronunciation audio: {e}")

        if not random_word.phonetic_us and us_pronunciation_link:
            try:
                download_and_save_audio(us_pronunciation_link, random_word, "us")
            except Exception as e:
                logging.error(f"Failed to download US pronunciation audio: {e}")

        logging.info(f"Word: {random_word.word}, Phonetic: {phonetic}")
        logging.info(f"UK Pronunciation Link: {uk_pronunciation_link}")
        logging.info(f"US Pronunciation Link: {us_pronunciation_link}")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return "发生错误"

    end_time = time.time()
    logging.info(f"查询耗时：{end_time - start_time}秒")

    return f"单词: {random_word.word}"


def download_and_save_audio(url, word, language):
    try:
        logging.info("--------------------------------------------------")
        logging.info(f"下载音频 URL: {url}")
        logging.info("--------------------------------------------------")

        # 构建相对路径（相对于 MEDIA_ROOT）
        if language == "us":
            relative_path = f"audio/us/{word.word}.mp3"
        else:
            relative_path = f"audio/uk/{word.word}.mp3"

        # 检查文件是否已经存在
        full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        if default_storage.exists(relative_path):
            logging.info(f"音频文件 {relative_path} 已经存在，跳过下载")

            # 检查数据库中是否存在相应的 AudioFile 记录
            audio_file_obj = AudioFile.objects.filter(word_text=word.word, language=language).first()
            if not audio_file_obj:
                logging.info(f"数据库中不存在 {relative_path} 的记录，创建并保存记录")

                # 创建并保存 AudioFile 对象
                audio_file_obj = AudioFile(
                    word_text=word.word,
                    file_path=relative_path,  # 存储相对路径
                    language=language
                )
                audio_file_obj.save()

                # 更新 Word 对象的音频字段
                if language == "uk":
                    word.phonetic_uk = relative_path
                else:
                    word.phonetic_us = relative_path
                word.save()

            return

        # 下载音频文件
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            # 确保目录存在
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # 使用 Django 的 default_storage 保存文件
            with default_storage.open(relative_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logging.info(f"音频文件已保存为 {relative_path}")

            # 更新 Word 对象的音频字段
            if language == "uk":
                word.phonetic_uk = relative_path
            else:
                word.phonetic_us = relative_path
            word.save()

            # 创建并保存 AudioFile 对象
            audio_file_obj = AudioFile(
                word_text=word.word,
                file_path=relative_path,  # 存储相对路径
                language=language
            )
            audio_file_obj.save()

        else:
            logging.error(f"下载失败，状态码：{response.status_code}")
    except requests.exceptions.RequestException as e:
        logging.error(f"下载音频时发生异常: {e}")
    except Exception as e:
        logging.error(f"处理音频文件时发生未知异常: {e}")


# 提供单词音频地址
def get_audio_url(request, word):
    # audio_files = get_object_or_404(AudioFile, word_text=word)
    audio_file = AudioFile.objects.filter(word_text=word, language='us').first()
    if audio_file is None:
        logging.error(f"未找到单词 {word} 的美式发音音频文件")
        return {'error': '未找到音频文件'}
    # 获取数据库中的路径
    db_path = audio_file.file_path
    # 构建完整的音频文件 URL
    # audio_url = settings.MEDIA_ROOT / db_path
    audio_url = str(db_path)
    # 返回 JSON 响应
    logging.info(f"======hhhhhh======:{audio_url}")
    return {'audio_url': audio_url}


def get_youdao_data(word):
    if not word:
        logging.warning("输入的单词为空")
        return "", "", ""

    try:

        url = f"https://www.youdao.com/result?word={word}&lang=en"

        # 添加请求头伪装
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)

        # 检查请求是否成功
        if response.status_code == 200:
            tree = html.fromstring(response.content)

            # 使用XPath提取音标
            phonetic = tree.xpath('//span[@class="phonetic"]/text()')
            phonetic = phonetic[0].strip() if phonetic else ""

            # 获取翻译
            # 提取第一个 li 元素下的 span 文字
            trans_spans = tree.xpath('//ul[@class="basic"]/li[1]/span')
            trans_text = ' '.join(span.text.strip() for span in trans_spans if span.text)

            # 英式发音
            uk_pronunciation_link = f'https://dict.youdao.com/dictvoice?audio={word}&type=1'
            # 美式发音
            us_pronunciation_link = f'https://dict.youdao.com/dictvoice?audio={word}&type=2'

            return phonetic, trans_text, uk_pronunciation_link, us_pronunciation_link
        else:
            logging.error(f"请求失败，状态码：{response.status_code}")
            return "", "", "", ""
    except requests.exceptions.RequestException as e:
        logging.error(f"网络请求异常: {e}")
        return "", "", "", ""
