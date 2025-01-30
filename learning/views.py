import logging
import os
import random
import time
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.core.cache import cache
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


# 缓存键名常量
WORD_IDS_CACHE_KEY = 'all_word_ids'


def get_cached_word_ids():
    """
    获取缓存的单词 ID 列表，若不存在则从数据库加载
    """
    word_ids = cache.get(WORD_IDS_CACHE_KEY)
    if word_ids is None:
        word_ids = list(Word.objects.values_list('id', flat=True))
        cache.set(WORD_IDS_CACHE_KEY, word_ids, timeout=60 * 60 * 24)  # 缓存 24 小时
        logging.info("Refreshed word IDs cache")
    return word_ids


def word_card(request):
    start_time = time.time()
    context = {'word': None}

    try:
        # 1. 从缓存获取所有单词 ID
        word_ids = get_cached_word_ids()
        if not word_ids:
            logging.warning("No words found in database")
            return render(request, 'learning/word_card.html', context)

        # 2. 随机选择一个 ID 并查询完整对象
        random_id = random.choice(word_ids)
        random_word = Word.objects.get(id=random_id)
        logging.info(f"Selected word: {random_word}")

        context['word'] = random_word

    except Word.DoesNotExist:
        # 处理缓存 ID 与实际数据不一致的情况（例如数据被删除）
        logging.warning(f"Word with id={random_id} not found, resetting cache")
        cache.delete(WORD_IDS_CACHE_KEY)  # 强制下次刷新缓存
        return render(request, 'learning/word_card.html', context)

    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        return render(request, 'learning/word_card.html', context)

    finally:
        # 记录耗时（无论成功与否）
        end_time = time.time()
        logging.info(f"Query time: {end_time - start_time:.4f}s")

    return render(request, 'learning/word_card.html', context)


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
