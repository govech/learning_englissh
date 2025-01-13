from django.contrib import admin

# Register your models here.
# 导入Django的admin模块，用于管理网站后台
from django.contrib import admin

# 从当前应用的models.py文件中导入Word模型
from .models import Word

# 将Word模型注册到Django的后台管理站点中
# 这样做使得后台管理员能够对Word模型的数据进行增删改查操作
admin.site.register(Word)

