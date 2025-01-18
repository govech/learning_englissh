from django.test import TestCase
from learning.my_utils.init_db_and_audio import word_card

class WordCardTests(TestCase):
    def test_word_card(self):
        result = word_card()
        self.assertIsNotNone(result)  # 根据实际需求添加断言
        print(f'Test result: {result}')