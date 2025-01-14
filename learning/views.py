from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect, get_object_or_404
from .models import Word


# Create your views here.


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
    word = get_object_or_404(Word, id=word_id)
    word.delete()
    return redirect('word_list')  # 重定向到单词列表页面

