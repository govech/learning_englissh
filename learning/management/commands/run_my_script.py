from django.core.management.base import BaseCommand
from learning.my_utils.init_db_and_audio import word_card

class Command(BaseCommand):
    help = 'Run the word_card test function'

    def handle(self, *args, **kwargs):
        result = word_card()
        self.stdout.write(self.style.SUCCESS(f'Test result: {result}'))