from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Vendedor
from .serializers import VendedorSerializer

class VendedorListCreateView(generics.ListCreateAPIView):
    queryset = Vendedor.objects.all()
    serializer_class = VendedorSerializer
    permission_classes = [IsAuthenticated]

class VendedorRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Vendedor.objects.all()
    serializer_class = VendedorSerializer
    permission_classes = [IsAuthenticated]
