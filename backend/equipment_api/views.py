from django.http import HttpResponse, HttpResponseNotFound, FileResponse
from django.shortcuts import redirect
import requests
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
import os

from .models import EquipmentDataset
from .serializers import EquipmentDatasetSerializer
from .services import parse_and_analyze
from .pdf_report import build_pdf_report


def index(request):
    # During development, prefer the React dev server so `src` files are used.
    # Proxy requests to the dev server so the app is available on the Django port.
    if settings.DEBUG:
        try:
            dev_url = f'http://localhost:3000{request.get_full_path()}'
            resp = requests.get(dev_url, timeout=1)
            content_type = resp.headers.get('Content-Type', 'text/html')
            return HttpResponse(resp.content, content_type=content_type, status=resp.status_code)
        except Exception:
            # Dev server not running or request failed — fall back to redirect so
            # developer can still open the app directly if desired.
            try:
                return redirect('http://localhost:3000/')
            except Exception:
                pass

    index_path = settings.BASE_DIR / 'frontend_web' / 'build' / 'index.html'
    if not index_path.exists():
        return HttpResponseNotFound(
            "Frontend build not found. Run `npm run build` and commit the build folder."
        )
    return FileResponse(open(index_path, 'rb'), content_type='text/html')


MAX_STORED_DATASETS = 5


def trim_to_last_n(user=None):
    qs = EquipmentDataset.objects.all()
    if user and user.is_authenticated:
        qs = qs.filter(uploaded_by=user)
    qs = qs.order_by('-created_at')
    to_delete = list(qs[MAX_STORED_DATASETS:].values_list('id', flat=True))
    if to_delete:
        EquipmentDataset.objects.filter(id__in=to_delete).delete()


class CSVUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        file_obj = request.FILES.get('file') or request.data.get('file')
        if not file_obj:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        name = request.data.get('name', file_obj.name or 'Untitled')

        try:
            summary = parse_and_analyze(file_obj)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        dataset = EquipmentDataset(
            name=name,
            uploaded_by=request.user if request.user.is_authenticated else None,
            total_count=summary['total_count'],
            avg_flowrate=summary.get('avg_flowrate'),
            avg_pressure=summary.get('avg_pressure'),
            avg_temperature=summary.get('avg_temperature'),
            type_distribution=summary.get('type_distribution', {}),
            raw_rows=summary.get('raw_rows', []),
        )
        dataset.save()
        trim_to_last_n(request.user)

        serializer = EquipmentDatasetSerializer(dataset)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SummaryView(APIView):

    def get(self, request, dataset_id):
        try:
            dataset = EquipmentDataset.objects.get(pk=dataset_id)
        except EquipmentDataset.DoesNotExist:
            return Response({'error': 'Dataset not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = EquipmentDatasetSerializer(dataset)
        return Response(serializer.data)


class HistoryListView(APIView):

    def get(self, request):
        qs = EquipmentDataset.objects.all().order_by('-created_at')[:MAX_STORED_DATASETS]
        serializer = EquipmentDatasetSerializer(qs, many=True)
        return Response(serializer.data)


class PDFReportView(APIView):

    def get(self, request, dataset_id):
        try:
            dataset = EquipmentDataset.objects.get(pk=dataset_id)
        except EquipmentDataset.DoesNotExist:
            return Response({'error': 'Dataset not found'}, status=status.HTTP_404_NOT_FOUND)
        pdf_bytes = build_pdf_report(dataset)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="equipment_report_{dataset_id}.pdf"'
        return response
