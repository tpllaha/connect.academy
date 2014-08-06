from django.conf import settings
from django.contrib import admin

from .models import *

admin.site.register(jUser)
admin.site.register(StudentCourseRegistration)
admin.site.register(ProfessorCourseRegistration)
admin.site.register(Major)
admin.site.register(Course)
admin.site.register(CourseTopic)
admin.site.register(Tag)
admin.site.register(University)
admin.site.register(Category)
admin.site.register(Domain)
admin.site.register(Deadline)
admin.site.register(CourseRegistrationDeadline)
admin.site.register(Rating)
admin.site.register(Review)
admin.site.register(CourseDocument)
admin.site.register(CourseHomeworkRequest)
admin.site.register(CourseHomeworkSubmission)
admin.site.register(Forum)
admin.site.register(ForumTag)
admin.site.register(ForumTopicTag)
admin.site.register(ForumExtraTag)
admin.site.register(ForumPost)
admin.site.register(ForumAnswer)
admin.site.register(WikiContributions)
admin.site.register(WikiPage)
admin.site.register(Appointment)
admin.site.register(PersonalAppointment)
admin.site.register(CourseAppointment)
