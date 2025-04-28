from .models import Notification

def notifications(request):
    if request.user.is_authenticated:
        unread_notifications = Notification.objects.filter(
            user=request.user,
            read=False
        ).order_by('-created_at')
        return {
            'notifications': unread_notifications,
            'notification_count': unread_notifications.count()
        }
    return {'notifications': [], 'notification_count': 0}

def theme(request):
    if request.user.is_authenticated:
        theme = request.user.profile.preference
    else:
        theme = request.session.get('theme', 'light')
    return {'theme': theme} 