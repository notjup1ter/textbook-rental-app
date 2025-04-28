from .models import Notification

def notifications(request):
    if request.user.is_authenticated:
        unread_notifications = Notification.objects.filter(
            user=request.user,
            read=False
        ).order_by('-created_at')[:5]
        return {'unread_notifications': unread_notifications}
    return {'unread_notifications': []}

def theme(request):
    if request.user.is_authenticated:
        theme = request.user.profile.preference
    else:
        theme = request.session.get('theme', 'light')
    return {'theme': theme} 