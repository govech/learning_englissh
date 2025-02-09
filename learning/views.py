import json
import logging
import os
import time
from itertools import chain

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

import random
from .models import Word, AudioFile, UserWord
from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from .models import DailyTask, TaskWord, UserWord

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


@login_required
def word_card(request):
    """
    显示单词学习卡片的核心视图
    包含进度计算、任务状态检查和动态内容加载
    """
    user = request.user
    today = timezone.localdate()

    # 获取或创建当日任务
    task, created = DailyTask.objects.get_or_create(
        user=user,
        date=today,
        defaults={'is_completed': False}
    )

    # 如果新创建任务或任务为空，生成学习内容
    if created or not task.taskword_set.exists():
        generate_daily_task(request, task)  # 直接传递任务对象
    # 检查任务完成状态
    if task.is_completed:
        return render(request, 'learning/review_complete.html')

    # 获取学习进度数据
    total_words = task.taskword_set.count()
    completed_words = task.taskword_set.filter(status='known').count()
    progress = int((completed_words / total_words) * 100) if total_words > 0 else 0

    # 获取下一个需要学习的单词
    task_word = (
        TaskWord.objects
            .filter(task=task, status__in=['new', 'retry'])
            .select_related('word__word')
            .order_by('-word__priority')
            .first()
    )

    # 如果没有待学习单词，标记任务完成
    if not task_word:
        task.is_completed = True
        task.save()
        return render(request, 'learning/review_complete.html')

    # 准备上下文数据
    context = {
        'task_id': task.id,
        'word': {
            'id': task_word.word.id,
            'word': task_word.word.word.word,
            'phonetic': task_word.word.word.phonetic,
            'definition': task_word.word.word.definition,
            'example': task_word.word.word.example,
            'audio_url': task_word.word.word.phonetic_us if task_word.word.word.phonetic_us else None,
        },
        'progress': progress,
        'remaining': total_words - completed_words,
    }

    return render(request, 'learning/word_card.html', context)


def select_words_for_today(user, total_new_words=20):
    """
    为用户选择今天需要学习的单词，包括新单词和复习单词。
    - user: 当前用户对象
    - total_new_words: 每天需要学习的单词数量（默认为20个）
    """
    # 获取所有单词
    all_words = Word.objects.all()

    # 获取用户的学习历史
    user_words = UserWord.objects.filter(user=user)

    # 获取所有新单词，即那些在 UserWord 表中不存在的单词
    learned_words = [uw.word for uw in user_words]
    new_words = [word for word in all_words if word not in learned_words]

    # 从新单词中随机选择 total_new_words 个单词
    new_words_today = random.sample(new_words, min(total_new_words, len(new_words)))

    # 获取需要复习的单词，按优先级从高到低排序
    review_words_today = user_words.exclude(word__in=new_words_today)  # 避免重复选择
    review_words_today = review_words_today.order_by('-priority')[:total_new_words]

    # 合并新单词和复习单词
    words_for_today = new_words_today + [uw.word for uw in review_words_today]

    return words_for_today


# 示例：每次用户登录时调用该方法，获取当天需要学习的单词
def get_daily_words(user):
    """
    获取每天需要学习的单词（包括新单词和复习单词）
    """
    # 获取今天需要学习的单词
    words_for_today = select_words_for_today(user)

    return words_for_today





@require_http_methods(["GET"])
def generate_daily_task(request, task):
    """生成当日学习任务"""
    user = request.user

    # 获取待复习单词（优先级排序）
    due_words = UserWord.get_due_words(user, limit=30)

    # 补充新单词：10个新单词
    new_words = UserWord.objects.filter(
        user=user,
        review_count=0
    ).exclude(pk__in=due_words.values_list('pk', flat=True))[10]

    # 创建任务关联
    task_words = chain(due_words, new_words)
    for word in task_words:
        status = 'retry' if word in due_words else 'new'
        TaskWord.objects.create(task=task, word=word, status=status)
    return JsonResponse({
        'task_id': task.id,
        'is_completed': task.is_completed,
        'words_count': task.words.count()
    })


@login_required
@require_http_methods(["POST"])
def handle_feedback(request):
    """处理用户反馈"""
    try:
        # 解析 JSON 数据
        data = json.loads(request.body)
        task_id = data.get('task_id')
        word_id = data.get('word_id')
        action = data.get('action')  # 前端发送的是 'know' 或 'forget'

        # 将 action 转换为 is_correct
        is_correct = action == 'know'

        # 获取任务和任务单词
        task = DailyTask.objects.get(pk=task_id)
        task_word = TaskWord.objects.get(task=task, word_id=word_id)

        # 更新单词状态
        task_word.status = 'known' if is_correct else 'retry'
        task_word.save()

        # 处理记忆算法
        user_word = task_word.word
        user_word.process_feedback(is_correct)

        # 检查任务完成状态
        task.check_completion()

        # 返回响应
        return JsonResponse({
            'success': True,
            'task_completed': task.is_completed,
            'new_priority': user_word.priority
        })
    except DailyTask.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Task not found'
        }, status=404)
    except TaskWord.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'TaskWord not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def daily_review(request):
    """每日复习主视图"""
    user = request.user

    # 获取或创建当日任务
    task, created = DailyTask.objects.get_or_create(
        user=user,
        date=timezone.localdate(),
        defaults={'is_completed': False}
    )

    # 生成任务内容（如果是新任务）
    if created or not task.taskword_set.exists():
        generate_daily_task(request, task)

    # 检查任务完成状态
    if task.is_completed:
        return render(request, 'learning/review_complete.html')

    # 获取下一个需要复习的单词
    task_word = TaskWord.objects.filter(
        task=task,
        status__in=['new', 'retry']
    ).select_related('word__word').order_by('-word__memory_strength').first()

    if not task_word:
        task.is_completed = True
        task.save()
        return render(request, 'learning/review_complete.html')

    context = {
        'task_id': task.id,
        'word': {
            'id': task_word.word.id,
            'text': task_word.word.word.text,
            'phonetic': task_word.word.word.phonetic,
            'definition': task_word.word.word.definition,
            'example': task_word.word.word.example,
        }
    }
    return render(request, 'learning/word_card.html', context)


def review_complete(request):
    """任务完成页面"""
    return render(request, 'learning/review_complete.html')


def get_next_word(request):
    """获取下一个单词的HTML片段"""
    # 复用 daily_review 的逻辑，但只返回单词卡片部分
    return daily_review(request)


def update_word_priority(user_word, feedback_type):
    if user_word is None:
        raise ValueError("user_word cannot be None")
    if not hasattr(user_word, 'correct_streak'):
        raise AttributeError("user_word missing required attributes")
    if feedback_type not in ['know', 'forget']:  # 明确允许的反馈类型
        raise ValueError("Invalid feedback_type")

    # 更新计数
    if feedback_type == 'know':
        user_word.correct_streak = max(1, user_word.correct_streak + 1)
        user_word.error_count = max(0, user_word.error_count - 1)
    else:
        user_word.error_count += 1
        user_word.correct_streak = max(-1, user_word.correct_streak - 2)  # 确保 correct_streak 不低于 -1

    # 计算记忆强度
    strength = 3.0 + 1.5 ** user_word.correct_streak - 0.8 * user_word.error_count
    strength = max(0.5, min(strength, 15.0)) * (0.95 + 0.1 * random.random())
    user_word.memory_strength = round(strength, 2)

    # 计算优先级
    days_since = (timezone.now() - user_word.last_review).days
    time_factor = 1.2 ** max(days_since - 3, 0)
    priority = (10 / (1 + strength ** 0.7)) * (1 + 0.3 * user_word.error_count) * time_factor
    user_word.priority = max(0.1, min(priority, 100.0))

    # 设置复习间隔
    if strength < 5:
        interval = 1
    elif strength < 10:
        interval = 3 + 0.5 * (strength - 5)
    else:
        interval = 5 * (1.5 ** ((strength - 10) / 5))

    user_word.next_review = timezone.now() + timedelta(days=min(round(interval), 30))

    # 合并属性更新，减少数据库操作
    user_word.save()


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
