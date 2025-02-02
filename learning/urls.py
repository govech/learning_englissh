# 导入Django的URL路径函数和当前应用的视图模块
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from . import views

# 定义URL模式列表，用于映射URL到视图函数
urlpatterns = [
    # 创建一个URL模式，将 '/words/' 路径映射到 'views.word_list' 视图函数
    # 这个模式命名为 'word_list'，便于在模板或其他视图中引用

    path('', views.home, name='home'),  # 首页
    path('words/', views.word_list, name='word_list'),  # 单词列表页
    path('word_card/', views.word_card, name='word_card'),  # 单词卡片页
    path('reading/', views.reading_page, name='reading_page'),  # 阅读页
    path('add_words/', views.add_words, name='add_words'),  # 添加单词页面
    path('delete_word/<int:word_id>/', views.delete_word, name='delete_word'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('audio/<str:word>/', views.get_audio_url, name='get_audio_url'),
    path('handle_feedback/', views.handle_feedback, name='handle_feedback'),
]
