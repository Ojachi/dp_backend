from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Distribuidor
from .serializers import DistribuidorSerializer

class DistribuidorListCreateView(generics.ListCreateAPIView):
    queryset = Distribuidor.objects.all()
    serializer_class = DistribuidorSerializer
    permission_classes = [IsAuthenticated]

class DistribuidorRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Distribuidor.objects.all()
    serializer_class = DistribuidorSerializer
    permission_classes = [IsAuthenticated]
