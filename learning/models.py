from django.contrib.auth.models import User

import math
import random
from django.db import models
from django.utils import timezone
from django.db import transaction


class Word(models.Model):
    """
    Word模型类，继承自Django的models.Model。
    用于在数据库中表示一个单词及其相关信息。

    属性:
    - word: 单词本身，最大长度为100字符。
    - definition: 单词的定义或解释，最大长度为100字符。
    - example: 使用该单词的例句或示例，长度不受限制。
    """
    word = models.CharField(max_length=100)
    definition = models.CharField(max_length=100)
    example = models.TextField()
    phonetic_uk = models.CharField(max_length=100, blank=True)  # 英音发音地址
    phonetic = models.CharField(max_length=100, blank=True)
    phonetic_us = models.CharField(max_length=100, blank=True)  # 美音发音地址
    rating = models.IntegerField(default=0, choices=[(i, str(i)) for i in range(0, 6)])  # 单词本身的难度评分

    def __str__(self):
        """
        返回单词本身的字符串表示。

        返回:
        - self.word: 单词本身。
        """
        return self.word


class UserWord(models.Model):
    """
    用户单词记忆模型，记录用户对特定单词的记忆信息
    包括记忆强度、复习时间、错误次数等

    优化点：
    1. 使用可调用默认值避免JSONField共享引用问题
    2. 移除未使用的lock_version字段
    3. 优化数据库索引
    4. 修正复习次数统计逻辑
    5. 添加字段说明提升可维护性
    6. 使用initial_strength字段参与计算
    """
    MEMORY_PHASE_CHOICES = [
        ('initial', '初次学习'),
        ('retention', '保持阶段'),
        ('mastered', '完全掌握')
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="用户",
        help_text="关联的用户账户"
    )
    word = models.ForeignKey(
        'Word',
        on_delete=models.CASCADE,
        verbose_name="单词",
        help_text="关联的单词"
    )
    memory_strength = models.FloatField(
        default=3.0,
        verbose_name="记忆强度",
        help_text="动态计算的记忆强度值，范围[0.5, 15.0]"
    )
    next_review = models.DateTimeField(
        default=timezone.now,
        verbose_name="下次复习时间",
        help_text="根据记忆算法计算的下次复习时间"
    )
    error_count = models.PositiveIntegerField(
        default=0,
        verbose_name="错误次数",
        help_text="累计回答错误次数"
    )
    last_review = models.DateTimeField(
        auto_now=True,
        verbose_name="最后复习时间",
        help_text="最后一次复习的时间戳"
    )
    priority = models.FloatField(
        default=0.0,
        verbose_name="复习优先级",
        help_text="动态计算的复习优先级，值越大优先级越高"
    )
    correct_streak = models.IntegerField(
        default=0,
        verbose_name="连续正确次数",
        help_text="最近连续回答正确的次数（允许负值表示连续错误）"
    )
    review_count = models.PositiveIntegerField(
        default=0,
        verbose_name="复习次数",
        help_text="总复习次数（含正确和错误）"
    )
    history_intervals = models.JSONField(
        default=list,
        verbose_name="历史间隔记录",
        help_text="存储历次复习间隔的JSON数组"
    )
    memory_phase = models.CharField(
        max_length=20,
        choices=MEMORY_PHASE_CHOICES,
        default='initial',
        verbose_name="记忆阶段",
        help_text="当前记忆阶段：initial/retention/mastered"
    )
    initial_strength = models.FloatField(
        default=3.0,
        verbose_name="初始强度",
        help_text="记忆初始强度值，参与记忆强度计算"
    )

    class Meta:
        unique_together = ('user', 'word')
        indexes = [
            # 优化复合索引，覆盖常用查询条件
            models.Index(
                fields=['user', 'next_review', '-priority'],
                name='user_next_priority_idx'
            ),
            # 保留单独索引用于特殊排序需求
            models.Index(fields=['priority'], name='priority_idx'),
        ]
        verbose_name = "用户单词记忆"
        verbose_name_plural = "用户单词记忆记录"

    def __str__(self):
        return f"{self.user.username} - {self.word}"

    def update_memory_strength(self):
        """更新记忆强度（含随机波动）"""
        # 使用initial_strength参与计算
        base = self.initial_strength + 1.5 ** self.correct_streak
        penalty = 0.8 * math.log1p(self.error_count)
        noise = random.uniform(0.95, 1.05)  # ±5%波动

        self.memory_strength = max(0.5, min(
            (base - penalty) * noise,
            15.0
        ))
        return self.memory_strength

    def calculate_priority(self):
        """计算动态优先级"""
        time_diff = timezone.now() - self.last_review
        days_since = time_diff.days + time_diff.seconds / 86400  # 精确到小数天数
        time_factor = 1.2 ** max(days_since - 3, 0)

        priority = (
                (10 / (1 + self.memory_strength ** 0.7)) *
                (1 + 0.3 * math.log1p(self.error_count)) *
                time_factor *
                (2.0 if self.memory_phase == 'initial' else 1.0)
        )
        self.priority = max(0.1, min(priority, 100.0))
        return self.priority

    @classmethod
    def get_due_words(cls, user, limit=50):
        """获取待复习单词列表，确保所有单词都能被复习到"""
        due_words = cls.objects.filter(
            user=user,
            next_review__lte=timezone.now()
        ).order_by('-priority')

        # 如果待复习单词数量超过限制，则分批次返回
        if due_words.count() > limit:
            # 获取优先级最高的前 limit//2 个单词
            high_priority_words = due_words[:limit // 2]

            # 获取剩余单词中随机选取 limit//2 个单词
            remaining_words = due_words[limit // 2:].order_by('?')[:limit // 2]

            # 合并两部分单词
            due_words = high_priority_words | remaining_words

        return due_words

    @transaction.atomic
    def process_feedback(self, is_correct):
        """处理用户反馈的原子操作（返回更新后的实例）"""
        # 获取并锁定记录（使用select_for_update保证原子性）
        obj = UserWord.objects.select_for_update().get(pk=self.pk)

        # 更新基础数据（无论对错都增加复习次数）
        obj.review_count += 1

        if is_correct:
            obj.correct_streak += 1
            obj.error_count = max(0, obj.error_count - 1)
        else:
            obj.correct_streak = max(-2, obj.correct_streak - 2)  # 允许最低到-2
            obj.error_count += 1

        # 动态调整记忆阶段
        if obj.review_count >= 4 and obj.error_count == 0:
            obj.memory_phase = 'mastered'
        elif obj.review_count > 1:
            obj.memory_phase = 'retention'
        else:
            obj.memory_phase = 'initial'

        # 计算记忆参数
        obj.update_memory_strength()
        obj.calculate_priority()
        interval = obj._calculate_interval()

        # 记录历史间隔（使用可序列化的时间格式）
        obj.history_intervals.append({
            'date': timezone.now().isoformat(),
            'interval': interval,
            'correct': is_correct,
            'strength': round(obj.memory_strength, 2)
        })

        # 设置下次复习时间（添加时间微调防止批量重复）
        jitter = random.uniform(0.9, 1.1)  # ±10%时间波动
        obj.next_review = timezone.now() + timezone.timedelta(
            days=interval * jitter
        )
        obj.save()

        # 更新当前实例状态
        self.__dict__.update(obj.__dict__)
        return self

    def _calculate_interval(self):
        """间隔计算算法（带自适应调整）"""
        base_intervals = [1, 2, 4, 7, 12, 21]  # 改进的基础间隔序列

        # 根据复习次数选择基础间隔
        idx = min(self.review_count - 1, len(base_intervals) - 1)
        base_interval = base_intervals[idx] if idx >= 0 else 1

        # 错误惩罚机制
        if self.error_count >= 2:
            interval = max(1, base_interval // 2)
        # 连续正确奖励机制
        elif self.correct_streak >= 3:
            interval = min(base_interval * 2, 60)
        else:
            interval = base_interval

        # 添加随机波动（避免完全规律性）
        return round(interval * random.uniform(0.9, 1.1), 1)


# class UserWord(models.Model):
#     MEMORY_PHASE_CHOICES = [
#         ('initial', '初次学习'),
#         ('retention', '保持阶段'),
#         ('mastered', '完全掌握')
#     ]
#
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     word = models.ForeignKey('Word', on_delete=models.CASCADE)
#     memory_strength = models.FloatField(default=3.0)
#     next_review = models.DateTimeField(default=timezone.now)
#     error_count = models.IntegerField(default=0)
#     last_review = models.DateTimeField(auto_now=True)
#     priority = models.FloatField(default=0.0)
#     correct_streak = models.IntegerField(default=0)
#     review_count = models.IntegerField(default=0)
#     history_intervals = models.JSONField(default=list)
#     lock_version = models.IntegerField(default=0)
#     memory_phase = models.CharField(
#         max_length=20,
#         choices=MEMORY_PHASE_CHOICES,
#         default='initial'
#     )
#     initial_strength = models.FloatField(default=3.0)
#
#     class Meta:
#         unique_together = ('user', 'word')
#         indexes = [
#             models.Index(fields=['user', 'next_review']),
#             models.Index(fields=['priority']),
#         ]
#
#     def __str__(self):
#         return f"{self.user.username} - {self.word}"
#
#     def update_memory_strength(self):
#         """更新记忆强度（含随机波动）"""
#         base = 3.0 + 1.5 ** self.correct_streak
#         penalty = 0.8 * math.log1p(self.error_count)
#         noise = random.uniform(0.95, 1.05)  # ±5%波动
#
#         self.memory_strength = max(0.5, min(
#             (base - penalty) * noise,
#             15.0
#         ))
#         return self.memory_strength
#
#     def calculate_priority(self):
#         """计算动态优先级"""
#         days_since = (timezone.now() - self.last_review).days
#         time_factor = 1.2 ** max(days_since - 3, 0)
#
#         priority = (
#                 (10 / (1 + self.memory_strength ** 0.7)) *
#                 (1 + 0.3 * math.log1p(self.error_count)) *
#                 time_factor *
#                 (2.0 if self.memory_phase == 'initial' else 1.0)
#         )
#         self.priority = max(0.1, min(priority, 100.0))
#         return self.priority
#
#     @classmethod
#     def get_due_words(cls, user, limit=50):
#         """获取待复习单词列表"""
#         return cls.objects.filter(
#             user=user,
#             next_review__lte=timezone.now()
#         ).order_by('-priority')[:limit]
#
#     @transaction.atomic
#     def process_feedback(self, is_correct):
#         """处理用户反馈的原子操作"""
#         # 获取并锁定记录
#         obj = UserWord.objects.select_for_update().get(pk=self.pk)
#
#         # 更新基础数据
#         if is_correct:
#             obj.correct_streak += 1
#             obj.review_count += 1
#             obj.error_count = max(0, obj.error_count - 1)
#         else:
#             obj.correct_streak = max(-1, obj.correct_streak - 2)
#             obj.error_count += 1
#
#         # 更新记忆阶段
#         if obj.review_count >= 4 and obj.error_count == 0:
#             obj.memory_phase = 'mastered'
#         elif obj.review_count > 1:
#             obj.memory_phase = 'retention'
#
#         # 计算记忆参数
#         obj.update_memory_strength()
#         obj.calculate_priority()
#         interval = obj._calculate_interval()
#
#         # 记录历史间隔
#         obj.history_intervals.append({
#             'date': timezone.now().isoformat(),
#             'interval': interval,
#             'correct': is_correct
#         })
#
#         # 设置下次复习时间
#         obj.next_review = timezone.now() + timezone.timedelta(days=interval)
#         obj.save()
#         return obj
#
#     def _calculate_interval(self):
#         """艾宾浩斯间隔计算核心算法"""
#         base_intervals = [1, 7, 16, 30]
#         idx = min(self.review_count - 1, len(base_intervals) - 1)
#
#         # 错误惩罚规则
#         if self.error_count >= 2:
#             interval = max(1, base_intervals[idx] // 2)
#         # 连续正确奖励
#         elif self.correct_streak >= 3:
#             interval = min(base_intervals[-1] * 2, 60)
#         else:
#             interval = base_intervals[idx]
#
#         # 添加±10%随机波动
#         return round(interval * random.uniform(0.9, 1.1), 1)


class DailyTask(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    is_completed = models.BooleanField(default=False)
    words = models.ManyToManyField(UserWord, through='TaskWord')

    class Meta:
        unique_together = ('user', 'date')

    def check_completion(self):
        """检查任务是否全部完成"""
        incomplete = self.taskword_set.filter(status__in=['new', 'retry']).exists()
        self.is_completed = not incomplete
        self.save()
        return self.is_completed


class TaskWord(models.Model):
    STATUS_CHOICES = [
        ('new', '新单词'),
        ('retry', '需复习'),
        ('known', '已掌握')
    ]

    task = models.ForeignKey(DailyTask, on_delete=models.CASCADE)
    word = models.ForeignKey(UserWord, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='new')

    class Meta:
        unique_together = ('task', 'word')


class AudioFile(models.Model):
    # 读音对应的单词
    word_text = models.CharField(max_length=100, blank=True, null=True)  # 存储对应的单词名称
    file_path = models.CharField(max_length=100, blank=True, null=True)  # 存储对应的发音文件路径

    LANGUAGE_CHOICES = [
        ('uk', 'UK'),
        ('us', 'US'),
    ]
    # 存储英音还是美音
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, blank=False, null=False)

    def __str__(self):
        return self.word_text


# class UserWordProgress(models.Model):
#     """用户学习进度模型
#
#     该模型记录用户对某个单词的学习进度，包括是否已记住、复习次数、最近一次复习时间及下次复习时间
#     """
#     # 关联用户，当用户被删除时，级联删除该用户的学习进度记录
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     # 关联单词，当单词被删除时，级联删除该单词的学习进度记录
#     word = models.ForeignKey(Word, on_delete=models.CASCADE)
#     # 记录用户是否已记住该单词，默认为否
#     is_memorized = models.BooleanField(default=False)
#     # 记录用户对单词的复习次数，默认为0
#     review_count = models.IntegerField(default=0)
#     # 记录用户最近一次复习该单词的时间，默认为当前时间
#     last_review_time = models.DateTimeField(default=timezone.now)
#     # 记录用户下次复习该单词的时间，默认为当前时间
#     next_review_time = models.DateTimeField(default=timezone.now)
#     # 复习间隔，初始为1天
#     review_interval = models.IntegerField(default=1)
#
#     STATUS_CHOICES = [
#         (0, '新单词'),
#         (1, '熟练度1'),
#         (2, '熟练度2'),
#         (3, '熟练度3'),
#         (4, '熟练度4'),
#         (5, '熟练度5'),
#     ]
#     # 状态：0 (新单词), 1-5(熟练度)
#     status = models.IntegerField(choices=STATUS_CHOICES, default=0)
#
#     def clean(self):
#         if self.status not in dict(self.STATUS_CHOICES):
#             raise ValidationError(f"无效的状态值: {self.status}")
#     def update_review(self, rating):
#         """
#         根据评分更新复习间隔和复习日期。
#         :param rating: 用户评分，表示记忆情况。
#         """
#         if rating == 5:
#             self.review_interval *= 2  # 间隔加倍
#         elif rating == 4:
#             self.review_interval = int(self.review_interval * 1.5)  # 略微延长
#         elif rating == 3:
#             pass  # 保持当前间隔
#         elif rating == 2:
#             self.review_interval = max(1, self.review_interval - 1)  # 缩短复习间隔
#         elif rating == 1:
#             self.review_interval = 1  # 完全忘记，重置间隔为1
#
#         # 更新复习日期
#         self.next_review_date = timezone.now() + timedelta(days=self.review_interval)
#         self.save()
#
#     # 确保同一个用户对同一个单词的学习进度是唯一的
#     class Meta:
#         unique_together = ['user', 'word']


class Article(models.Model):
    """
    Article模型类，继承自Django的models.Model。
    用于在数据库中表示一篇文章及其相关信息。

    属性:
    - title: 文章的标题，最大长度为100字符。
    - content: 文章的正文内容，长度不受限制。
    - difficulty : 难度等级，取值范围从1到5。

    """
    title = models.CharField(max_length=200)
    content = models.TextField()
    difficulty = models.CharField(max_length=20, choices=[('1', 'easy'), ('2', 'medium'), ('3', 'hard')])

    def __str__(self):
        """
        返回文章的标题字符串表示。
        """
        return self.title
