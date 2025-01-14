from django.shortcuts import render
from .models import Word


# Create your views here.


def home(request):
    return render(request, 'learning/home.html')


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
    return render(request, 'learning/word_card.html')


def reading_page(request):
    # 这里实现阅读页的功能
    return render(request, 'learning/reading_page.html')
