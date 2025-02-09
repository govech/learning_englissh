import random

from django.utils import timezone
from datetime import timedelta
from learning.models import UserWord

"""
一个基于用户反馈调整优先级的算法
"""

"""
每次用户反馈后，我们需要更新单词的优先级。如果用户标记为“认识”，记忆强度增加，优先级降低；如果标记为“不认识”，记忆强度减少，优先级提高。
"""


def update_word_priority(user_word, feedback_type):
    """
    根据用户反馈更新单词的优先级。
    feedback_type: 用户的反馈类型，'known' 或 'not_known'
    """
    # 获取当前单词的记忆强度
    strength = calculate_strength(user_word.correct_streak, user_word.incorrect_count)

    # 根据反馈调整记忆强度
    if feedback_type == 'known':
        user_word.correct_streak += 1  # 正确的反馈
        user_word.incorrect_count = 0  # 错误次数重置
    elif feedback_type == 'not_known':
        user_word.correct_streak = 0  # 错误的反馈
        user_word.incorrect_count += 1  # 错误次数增加

    # 计算新的优先级
    new_priority = calculate_priority(strength, user_word.incorrect_count)

    # 更新优先级
    user_word.priority = new_priority
    user_word.save()


"""
优先级的计算会根据记忆强度以及错误次数来调整。随着记忆强度的提高，优先级降低的幅度逐渐减小。
"""


def calculate_priority(strength, incorrect_count):
    """
    计算优先级，基于记忆强度和错误次数调整，并确保最低优先级阈值。
    """
    # 优先级是强度的倒数，强度越大，优先级越低
    priority = 1.0 / (1 + strength)  # 强度越大，优先级越低

    # 错误次数增加，优先级不能降得太低
    priority = max(0.2, priority * (1 - 0.1 * incorrect_count))  # 错误次数增加，优先级下降幅度小

    return priority


"""
记忆强度的计算会考虑单词的正确次数和错误次数。正确次数越多，记忆强度越高；错误次数越多，记忆强度越低
"""


def calculate_strength(correct_count, incorrect_count):
    """
    根据正确次数和错误次数计算记忆强度。
    正确次数越多，记忆强度越强；错误次数越多，记忆强度越弱。
    """
    strength = 1 + 0.2 * correct_count - 0.3 * incorrect_count
    strength = max(0.1, strength)  # 强度不能低于0.1
    return strength



"""
使用场景：
1、新用户注册时
当用户首次注册成功后，自动初始化学习计划

2、批量导入单词时
当用户一次性导入大量新单词后，批量设置初始复习时间

3、系统数据迁移时
历史数据迁移后，重新计算复习计划
"""
def calculate_initial_schedule(user):
    """初始化用户学习计划"""
    words = UserWord.objects.filter(user=user)

    for word in words:
        if word.review_count == 0:
            # 新单词初始间隔
            word.next_review = timezone.now() + timedelta(
                days=random.randint(1, 3)
            )
            word.save()
