from rest_framework import serializers
from .models import Distribuidor

class DistribuidorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Distribuidor
        fields = '__all__'
