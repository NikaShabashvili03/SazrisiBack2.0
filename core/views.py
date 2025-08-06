from django.shortcuts import render

def doc_view(request):
    return render(request, 'doc.html')