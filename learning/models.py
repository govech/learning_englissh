from django.db import models


# Create your models here.

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

    def __str__(self):
        """
        返回单词本身的字符串表示。

        返回:
        - self.word: 单词本身。
        """
        return self.word


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
