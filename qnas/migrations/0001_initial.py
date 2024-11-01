# Generated by Django 4.2 on 2024-11-01 12:44

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='QnA',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100)),
                ('content', models.TextField()),
                ('category', models.CharField(choices=[('U', '계정 문의'), ('E', '게임 실행 문의'), ('R', '게임 등록 문의')], max_length=1)),
                ('is_visible', models.BooleanField(default=True)),
            ],
        ),
    ]
