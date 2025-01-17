import logging
import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.core.files import File
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from .models import Word, AudioFile
import requests
from lxml import html

# Create your views here.

# 设置日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def home(request):
    return render(request, 'learning/home.html')


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # 注册后自动登录
            return redirect('home')  # 重定向到主页
    else:
        form = UserCreationForm()
    return render(request, 'learning/register.html', {'form': form})


def word_list(request):
    """
    获取所有单词并渲染到单词列表页面。

    从数据库中获取所有单词对象，然后将这些单词数据传递给模板进行渲染。
    这个函数定义了一个视图，该视图响应于HTTP请求，返回包含所有单词的页面。

    参数:
    - request: HttpRequest对象，表示用户的请求。

    返回:
    - HttpResponse对象，包含渲染后的页面，展示所有单词的列表。
    """
    # 从数据库中获取所有的单词对象
    words = Word.objects.all()
    # 渲染模板并返回HttpResponse对象
    return render(request, 'learning/word_list.html', {'words': words})


def word_card(request):
    # 这里实现单词卡片的功能
    random_word = Word.objects.order_by('?').first()

    # 如果单词没有中文意思，调用翻译 API 获取并保存
    if not random_word.definition:
        phonetic, chinese_meaning, uk_pronunciation_link, us_pronunciation_link = get_youdao_data(random_word)
        if chinese_meaning:
            random_word.definition = chinese_meaning
            random_word.phonetic = phonetic
            random_word.save()  # 保存到数据库

    if not random_word.phonetic_uk:
        if uk_pronunciation_link:
            download_and_save_audio(uk_pronunciation_link, random_word, "uk")

    if not random_word.phonetic_us:
        if us_pronunciation_link:
            download_and_save_audio(us_pronunciation_link, random_word, "us")

    print(f"Word: {random_word}, Phonetic: {phonetic}")
    print(f"UK Pronunciation Link: {uk_pronunciation_link}")
    print(f"US Pronunciation Link: {us_pronunciation_link}")

    return render(request, 'learning/word_card.html', {'word': random_word})


def download_and_save_audio(url, word, language):
    try:
        logging.info("--------------------------------------------------")
        logging.info(f"下载音频 URL: {url}")
        logging.info("--------------------------------------------------")

        # 下载音频文件
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            # 构建相对路径（相对于 MEDIA_ROOT）
            if language == "us":
                relative_path = f"audio/us/{word.word}.mp3"
            else:
                relative_path = f"audio/uk/{word.word}.mp3"

            # 确保目录存在
            full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
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
    audio_file = AudioFile.objects.filter(word_text=word, language='us')

    # 获取数据库中的路径
    db_path = audio_file.first().file_path
    # 构建完整的音频文件 URL
    # audio_url = settings.MEDIA_ROOT / db_path
    audio_url = str(db_path)
    # 返回 JSON 响应
    logging.info(f"======hhhhhh======:{audio_url}")
    return JsonResponse({'audio_url': audio_url})


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


def reading_page(request):
    # 这里实现阅读页的功能
    return render(request, 'learning/reading_page.html')


def add_words(request):
    if request.method == "POST":
        words_text = request.POST.get('words', '')  # 获取文本区域中的数据
        if words_text:
            lines = words_text.strip().split('\n')  # 按行分割文本
            for line in lines:
                word = line.strip()  # 去除多余空格
                if word:  # 如果行不为空
                    # 添加到数据库（假设没有音标和释义时）
                    Word.objects.get_or_create(word=word)
            return redirect('word_list')  # 保存成功后重定向到单词列表页
    return render(request, 'learning/add_words.html')


def delete_word(request, word_id):
    word = get_object_or_404(Word, id=word_id)
    word.delete()
    return redirect('word_list')  # 重定向到单词列表页面
