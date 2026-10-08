from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="googleoauthstate",
            name="browser_nonce_hash",
        ),
    ]
