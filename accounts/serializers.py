from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password

User=get_user_model()


class RegistrationSerializer(serializers.ModelSerializer):
    password =serializers.CharField(write_only=True,min_length=8,max_length=128)
    
    class Meta:
        model=User
        fields=['id','username','email','password']
        read_only_fields=['id']

    def validate(self,attrs):
        candidate=User(
            username=attrs['username'],
            email=attrs['email']
        )
        
        validate_password(attrs['password'],candidate)
        return attrs
    
    def create(self,validated_data):
        return User.objects.create_user(**validated_data)
    
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model=User
        fields=['id','username','email']
        read_only_fields=fields