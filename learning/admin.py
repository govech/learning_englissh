from django.contrib import admin

# Register your models here.
# 导入Django的admin模块，用于管理网站后台
from django.contrib import admin
from .models import UserWord, DailyTask, TaskWord
# 从当前应用的models.py文件中导入Word模型
from .models import Word

# 将Word模型注册到Django的后台管理站点中
# 这样做使得后台管理员能够对Word模型的数据进行增删改查操作
admin.site.register(Word)


# 用户词汇信息管理
@admin.register(UserWord)
class UserWordAdmin(admin.ModelAdmin):
    # 在列表中显示的字段
    list_display = ('user', 'word', 'memory_strength', 'next_review')
    # 过滤器，按记忆阶段筛选
    list_filter = ('memory_phase',)
    # 搜索字段，支持对词汇文本和用户名的搜索
    search_fields = ('word__text', 'user__username')


# 每日任务信息管理
@admin.register(DailyTask)
class DailyTaskAdmin(admin.ModelAdmin):
    # 在列表中显示的字段
    list_display = ('user', 'date', 'is_completed')
    # 按日期层次结构浏览
    date_hierarchy = 'date'


# 任务词汇信息管理
@admin.register(TaskWord)
class TaskWordAdmin(admin.ModelAdmin):
    # 在列表中显示的字段
    list_display = ('task', 'word', 'status')
    # 过滤器，按状态筛选
    list_filter = ('status',)
