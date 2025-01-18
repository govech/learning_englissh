import logging
import os
import random
import time
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Subquery, OuterRef
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import Word, AudioFile
import requests
from lxml import html

# Create your views here.

# 设置日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# 复习间隔：1天、2天、4天、7天、15天
REVIEW_INTERVALS = [1, 2, 4, 7, 15]


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
    获取单词列表并分页显示

    从数据库中获取所有的单词对象，并按 id 排序以确保分页顺序一致
    然后将这些单词对象分页，每页显示 50 条数据
    根据请求中的页码获取当前页的数据，并为每个单词对象计算全局序号
    最后将当前页的数据传递给模板进行渲染，并返回 HttpResponse 对象

    参数:
    request (HttpRequest): 客户端请求对象，包含请求方法、请求参数等信息

    返回:
    HttpResponse: 渲染后的页面内容
    """
    # 从数据库中获取所有的单词对象
    words = Word.objects.all().order_by('id')  # 按 id 排序，确保分页顺序一致

    # 分页，每页显示 50 条数据
    paginator = Paginator(words, 15)
    page_number = request.GET.get('page')  # 获取当前页码
    page_obj = paginator.get_page(page_number)  # 获取当前页的数据

    # 计算全局序号
    start_index = (page_obj.number - 1) * paginator.per_page  # 当前页的起始索引
    for index, word in enumerate(page_obj.object_list, start=start_index + 1):
        word.global_index = index  # 为每个单词对象添加全局序号

    # 渲染模板并返回 HttpResponse 对象
    return render(request, 'learning/word_list.html', {'page_obj': page_obj})



def word_card(request):
    start_time = time.time()

    try:
        # 获取所有在 Word 表中但不在 AudioFile 表中的数据的 ID 列表
        word_ids = list(Word.objects.exclude(
            word__in=AudioFile.objects.values('word_text')
        ).values_list('id', flat=True))

        if not word_ids:
            logging.warning("No words found in Word table that are not in AudioFile table.")
            return render(request, 'learning/word_card.html', {'word': None})

        # 随机选择一个 ID
        random_word_id = random.choice(word_ids)
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
        return render(request, 'learning/word_card.html', {'word': None})

    end_time = time.time()
    logging.info(f"查询耗时：{end_time - start_time}秒")

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
    audio_file = AudioFile.objects.filter(word_text=word, language='us').first()
    if audio_file is None:
        logging.error(f"未找到单词 {word} 的美式发音音频文件")
        return JsonResponse({'error': '未找到音频文件'}, status=404)
    # 获取数据库中的路径
    db_path = audio_file.file_path
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
    try:
        with transaction.atomic():
            word = get_object_or_404(Word, id=word_id)

            # 获取关联的 AudioFile 记录
            audio_files = AudioFile.objects.filter(word_text=word.word)

            # 尝试从数据库中删除单词对象及其关联的 AudioFile 记录
            for audio_file in audio_files:
                try:
                    audio_file.delete()
                except Exception as e:
                    logging.error(f"删除 AudioFile 数据库记录失败: {audio_file.id}, 错误信息: {e}")
                    raise  # 重新抛出异常以触发事务回滚

            try:
                word.delete()
            except Exception as e:
                logging.error(f"删除单词对象失败: {word.id}, 错误信息: {e}")
                raise  # 重新抛出异常以触发事务回滚

            # 如果所有数据库操作成功，则删除文件
            for audio_file in audio_files:
                if audio_file.file_path:
                    file_path = os.path.normpath(os.path.join(settings.MEDIA_ROOT, audio_file.file_path))
                    if os.path.exists(file_path) and str(file_path).startswith(str(settings.MEDIA_ROOT)):
                        try:
                            os.remove(file_path)
                            logging.info(f"已删除音频文件: {file_path}")
                        except OSError as e:
                            logging.error(f"删除音频文件失败: {file_path}, 错误信息: {e}")

    except Exception as e:
        logging.error(f"删除单词过程中发生错误: {e}")
        return redirect('word_list')

    return redirect('word_list')

# def start_learning_new_word(user, word_id):
#     """
#     用户开始学习新单词，初始化用户对单词的学习进度。
#     :param user: 当前用户
#     :param word_id: 单词ID
#     """
#     word = Word.objects.get(id=word_id)  # 获取指定ID的单词
#
#     # 创建学习进度记录
#     progress_instance = UserWordProgress.objects.create(
#         user=user,
#         word=word,
#         review_count=0,  # 初次学习时复习次数为0
#         last_review_time=timezone.now(),
#         next_review_time=timezone.now() + timedelta(days=REVIEW_INTERVALS[0]),  # 初次复习时间设为1天后
#         review_interval=REVIEW_INTERVALS[0],  # 初次复习间隔为1天
#         status=0  # 设置为新单词状态
#     )
#
#     return progress_instance
#
#
# def update_review_progress(progress_instance, rating):
#     """
#     根据用户评分（1-5）更新复习进度。
#     :param progress_instance: 当前单词的学习进度实例
#     :param rating: 用户评分，1-5之间
#     """
#     # 用户评分较低时，复习间隔缩短
#     if rating in [1, 2]:
#         # 如果评分较低，复习间隔缩短，最多退回1天
#         progress_instance.review_interval = max(1, progress_instance.review_interval - 1)
#     elif rating >= 3:
#         # 如果评分较高，增加复习间隔
#         current_index = REVIEW_INTERVALS.index(progress_instance.review_interval)
#         if current_index < len(REVIEW_INTERVALS) - 1:
#             progress_instance.review_interval = REVIEW_INTERVALS[current_index + 1]  # 增加间隔
#
#     # 更新复习日期
#     progress_instance.next_review_time = timezone.now() + timedelta(days=progress_instance.review_interval)
#     progress_instance.review_count += 1  # 增加复习次数
#     progress_instance.last_review_time = timezone.now()  # 更新最近复习时间
#     progress_instance.save()
#
#
# def get_words_to_review(user):
#     """
#     获取当前用户需要复习的单词。
#     :param user: 当前用户
#     :return: 需要复习的单词列表
#     """
#     return UserWordProgress.objects.filter(user=user, next_review_time__lte=timezone.now())
#
#
# def review_word(request):
#     """
#     用户复习单词的逻辑，显示需要复习的单词并更新进度。
#     :param request: 请求对象
#     :return: 渲染复习页面
#     """
#     user = request.user
#     words_to_review = get_words_to_review(user)  # 获取需要复习的单词
#
#     if words_to_review.exists():
#         word_to_review = words_to_review[0].word  # 获取待复习的单词
#
#         if request.method == 'POST':
#             # 用户提交评分
#             rating = int(request.POST['rating'])  # 假设评分是1-5
#             progress_instance = UserWordProgress.objects.get(user=user, word=word_to_review)
#             update_review_progress(progress_instance, rating)  # 更新复习进度
#             return redirect('review_word')  # 重定向到复习页面
#
#         return render(request, 'review_word.html', {'word': word_to_review})
#     else:
#         return render(request, 'no_words_to_review.html')  # 如果没有单词需要复习，显示无单词页面
#
#
# def learn_new_word(request):
#     """
#     引导用户学习新单词，随机选择未学习的单词。
#     :param request: 请求对象
#     :return: 渲染学习新单词页面
#     """
#     user = request.user  # 当前用户
#     unlearned_words = Word.objects.exclude(id__in=UserWordProgress.objects.filter(user=user).values('word_id'))
#
#     if unlearned_words.exists():
#         # 从未学习的单词中随机选择一个
#         word_to_learn = random.choice(unlearned_words)  # 随机选择一个未学习的单词
#         start_learning_new_word(user, word_to_learn.id)  # 开始学习该单词
#         return redirect('learn_word_page', word_id=word_to_learn.id)  # 跳转到学习该单词页面
#     else:
#         return render(request, 'all_words_learned.html')  # 如果所有单词都已学习，提示用户
