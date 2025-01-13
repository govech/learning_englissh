# 导入Django的URL路径函数和当前应用的视图模块
from django.urls import path
from . import views

# 定义URL模式列表，用于映射URL到视图函数
urlpatterns = [
    # 创建一个URL模式，将 '/words/' 路径映射到 'views.word_list' 视图函数
    # 这个模式命名为 'word_list'，便于在模板或其他视图中引用
    path('words/', views.word_list, name='word_list'),
]
