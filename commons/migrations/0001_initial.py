# Generated by Django 4.2 on 2025-06-20 12:40

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='UploadImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_id', models.PositiveIntegerField()),
                ('src', models.URLField(unique=True)),
                ('is_used', models.BooleanField(default=False)),
                ('create_dt', models.DateTimeField(auto_now_add=True)),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('uploader', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='upload_images', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
