import time

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from learning.my_utils.init_db_and_audio import word_card
from learning.utils.priority_adjustment_based_on_feedback import calculate_initial_schedule, initialize_user_words


class Command(BaseCommand):
    help = 'Run the word_card test function'

    def handle(self, *args, **kwargs):
        # while True:
        #     result = word_card()
        #     print(result)
        #     if not result:
        #         break
        #
        #     time.sleep(2)
        #     self.stdout.write(self.style.SUCCESS(f'Test result: {result}'))
        for user in User.objects.all():
            initialize_user_words(user)
            self.stdout.write(f"Initialized schedule for {user.username}")
