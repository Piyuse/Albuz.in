from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('albums', '0005_pendingphotodeletion')]

    operations = [
        migrations.AddField(model_name='album', name='category', field=models.CharField(choices=[('Travel', 'Travel'), ('Everyday', 'Everyday'), ('Together', 'Together')], default='Everyday', max_length=16)),
        migrations.AddField(model_name='album', name='color', field=models.CharField(default='#677a71', max_length=7)),
    ]
