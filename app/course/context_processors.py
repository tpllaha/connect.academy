from django.conf import settings
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils import timezone
from django.db.models import Q, F, Count, Avg, Sum
from aggregate_if import Count as CountIf, Sum as SumIf, Avg as AvgIf
from django.contrib.contenttypes.models import ContentType
from versioning.models import Revision

from app.models import *
from app.ratings import *
from app.forum.context_processors import forum_stats_context, forum_answer_context, forum_post_context

import itertools



def course_ratings_context(course, current_user=None):
    context = []
    types_dict = { key: val for key, val in RATING_TYPES }
    profs_dict = { prof.id: prof for prof in course.professors.all().annotate(
        score = Avg('rated__rating'), 
        count =  Count('rated'),
        my_score = SumIf('rated', only= Q(rated__user__id=current_user.id)) 
        )}
   
    other_ratings = course.rating_set.filter(~Q(rating_type=PROFESSOR_R)).values('rating_type').annotate(
        score=Avg('rating'), 
        count=Count('id'),
        my_score = SumIf('rating', only = Q(user__id=current_user.id))
        )

    for prof_id in profs_dict:
        prof = profs_dict[prof_id]
        context_rating = {
            'type_db': PROFESSOR_R,
            'type': types_dict[PROFESSOR_R],
            'score': prof.score if prof.count > 0 else None ,
            'count': prof.count,
            'my_score':  prof.my_score if prof.my_score > 0 else None,
            'professor': prof
        }
        context.append(context_rating)

    del types_dict[PROFESSOR_R] # Done with professors

    for r in other_ratings:
        context_rating = {
            'type_db': r['rating_type'],
            'type': types_dict[r['rating_type']],
            'score': r['score'],
            'count': r['count'],
            'my_score': r['my_score'] if r['my_score'] > 0 else None
        }
        context.append(context_rating)
        del types_dict[r['rating_type']] # Done with this rating type

    # Add an entry to the context for every remaining rating_type (with no scores)
    for rating_type in types_dict:
        context_rating = {
            'type_db': rating_type,
            'type': types_dict[rating_type],
            'score': None,
            'count': 0,
            'my_score': None
        }
        context.append(context_rating)

    
    return context

def review_context(comment, current_user=None):
    context_comment = {
        'comment': comment
    }
    votes = Review.objects.filter(id=comment.id).aggregate(
        upvotes = Count('upvoted_by'), 
        downvotes = Count('downvoted_by'),
        my_upvote = CountIf('upvoted_by', only = Q(upvoted_by__id=current_user.id)),
        my_downvote = CountIf('downvoted_by', only = Q(upvoted_by__id=current_user.id)))

    context_comment['upvotes'] = votes['upvotes']
    context_comment['downvotes']  = votes['downvotes']
    context_comment['upvoted'] = votes['my_upvote'] > 0
    context_comment['downvoted'] = votes['my_downvote'] > 0
    if not comment.anonymous:
        context_comment['posted_by'] = comment.posted_by

    if context_comment['downvotes'] >= 3:
        context_comment['dont_show'] = True
    if context_comment['downvotes'] >= 7:
        context_comment['dont_show_at_all'] = True

    return context_comment


def course_reviews_context(course, current_user=None):
    context = []
    reviews = course.review_set.all()
    for review in reviews:
        context.append(review_context(review, current_user))
    return context

def course_homework_count_submitted(course, homework_request):
    num_files = homework_request.number_files
    students = StudentCourseRegistration.objects.filter(course=course, is_approved=True)
    
    students = students.annotate(files_submitted=CountIf('student__coursehomeworksubmission', 
        only=Q(student__coursehomeworksubmission__homework_request__id=homework_request.id) ))
    
    cnt_submitted = students.filter(files_submitted=num_files).count()
    # Only 1 big ass query

    return cnt_submitted

def homework_context(hw, current_user):
    course = hw.course
    current_time = timezone.now()
    nr_students = StudentCourseRegistration.objects.filter(course=course, is_approved=True).count()

    within_deadline = hw.deadline.start <= current_time and current_time < hw.deadline.end
    is_allowed = course.get_registration_status(current_user) == COURSE_REGISTRATION_REGISTERED
    is_student = current_user.is_student_of(course)
    can_submit_homework = is_student and is_allowed and within_deadline
    
    homework_submissions = []
    if current_user.is_student_of(course):
        homework_submissions = CourseHomeworkSubmission.objects.filter(submitter=current_user, homework_request=hw)

    homework_submitted = course_homework_count_submitted(course, hw)

    context = {
        "homework": hw,
        "can_submit": can_submit_homework,
        "is_allowed": is_allowed,
        "previous_submissions": homework_submissions,
        "submitted": len(homework_submissions) == hw.number_files,
        "stats": {
            "submitted": homework_submitted,
            "students": nr_students
        }
    }
    if current_user.has_perm('assign_homework', course) or current_user.has_perm('grade_homework',course):
        context['active_hw'] = within_deadline
        context['coming_hw'] = hw.deadline.start > current_time
        context['past_hw'] = hw.deadline.end <= current_time

    return context

def course_homework_context(course, current_user, topic_id=None):
    context = []
    all_homework = None
    if topic_id:
        all_homework = course.coursehomeworkrequest_set.filter(course_topic__id = topic_id)
    else:
        all_homework = course.coursehomeworkrequest_set.all()
    for hw in all_homework:
        context.append(homework_context(hw, current_user))
    return context

def homework_dashboard_context(request, course, current_user):
    if not current_user.has_perm('grade_homework', course):
        raise Http404
    context = {}
    homework_requests = CourseHomeworkRequest.objects.filter(course=course)
    students = course.students.all().order_by('username')
    current_time = timezone.now()
    context['homework_requests'] = []

    for hw in homework_requests:
        all_submissions = CourseHomeworkSubmission.objects.filter(homework_request=hw)
        submissions_context = []
        for st in students:
            submissions = all_submissions.filter(submitter=st).order_by('file_number')
            submissions_context.append({
                'student': st,
                'submissions': submissions,
                'file_numbers': [str(s.file_number) for s in submissions]
            })

        total_numfiles = hw.number_files * len(students)
        if total_numfiles > 0:
            percentage_completed = 100.0 * all_submissions.count() / (hw.number_files * len(students))
        else:
            percentage_completed = 0
        context['homework_requests'].append({
            'homework': hw,
            'all_submissions': submissions_context,
            'percentage_completed': percentage_completed,
            'ended': hw.deadline.end < current_time
        })

    # Course syllabus for topic editing
    context['syllabus'] = course_syllabus_context(course,current_user)

    # Is teacher
    context['teacher'] = {
        'is_teacher': current_user.is_professor_of(course) or current_user.is_assistant_of(course)
    }

    return context



def course_syllabus_context(course, current_user):
    context = []
    for topic in course.course_topics.all():
        topic_context = {
            'topic': topic,
            'documents': topic.documents.all(),

        }
        if current_user.is_student_of(course) or current_user.is_assistant_of(course) or current_user.is_professor_of(course):
            topic_context['homework'] = course_homework_context(course,current_user, topic.id)

        context.append(topic_context)
    return context


# Professor extra settings
def course_teacher_dashboard(request, course, user):
    context = {
        'is_teacher': user.is_professor_of(course)  or user.is_assistant_of(course)
    }
    if not context['is_teacher']:
        return context

    context['can_mail_students'] = user.has_perm('mail_students', course)
    context['can_approve_registrations'] = user.has_perm('approve_registrations', course)
    context['can_manage_forum'] = user.has_perm('manage_forum', course)
    context['can_manage_resources'] = user.has_perm('manage_resources', course)
    context['can_assign_homework'] = user.has_perm('assign_homework', course)
    context['can_grade_homework'] = user.has_perm('grade_homework', course)
    context['can_manage_info'] = user.has_perm('manage_info', course)
    context['can_manage_assistants'] = user.is_professor_of(course)

    context['students'] = {}

    # From python docs when using groupby: Generally, the iterable needs to already be sorted on the same key function.
    student_registrations = StudentCourseRegistration.objects.filter(course=course).order_by('is_approved')

    for reg_approved, registrations in itertools.groupby(student_registrations, key = lambda reg: reg.is_approved):
        if reg_approved and context['can_mail_students']:
            context['students']['registered'] = list(registrations)
        elif not reg_approved and context['can_approve_registrations']:
            context['students']['pending'] = list(registrations)
   
    if context['can_manage_forum']:
        context['forum_stats'] = forum_stats_context(course.forum)

    context['assistants'] = []
    for ta in course.teaching_assistants.all():
        ta_context = {'user': ta, 'permissions': []}
        for perm in Course._meta.permissions:
            ta_context['permissions'].append({
                'name': perm[0],
                'description': perm[1],
                'owned': ta.has_perm(perm[0], course)
            })
        context['assistants'].append(ta_context)


    return context


def course_page_context(request, course):
    context = {}
    context['course'] = course
    context['hw_redirect_url'] = '/course/' + course.slug
    course_types = dict(COURSE_TYPES)
    # Course type seems to be not working?
    # context['course_type'] = course_types[course.course_type]
    context['professors'] = course.professors.all()

    # Current user
    current_user = None
    if request.user.is_authenticated():
        current_user = jUser.objects.get(id=request.user.id)

    # Ratings and comments
    context['ratings'] = course_ratings_context(course, current_user)
    context['comments'] = course_reviews_context(course, current_user)
    context['activities'] = course_activities(request, course)

    # Course path
    context['course_path'] = course.get_catalogue()
    context['semester'] = context['course_path'].split(" > ")[0] # This only works for the current Jacobs course catalogue. Needs to change 

    # User - Course Registration status (open|pending|registered|not allowed)
    registration_status = course.get_registration_status(current_user)
    registration_deadline = course.get_registration_deadline()  # course registration deadline

    # Is course registration open?
    registration_open = False
    if registration_deadline is not None:
        registration_open = registration_deadline.is_open()

    context['registration_status'] = registration_status
    context['registration_open'] = registration_open

    # Course syllabus
    context['syllabus'] = course_syllabus_context(course,current_user)

    # Course forum link
    context['forum'] = course.forum

    context['can_edit_wiki'] = course.can_edit_wiki(current_user)
    if hasattr(course, 'wiki'):
        context['wiki'] = course.wiki
        wiki_ctype = ContentType.objects.get(app_label="app", model="wikipage")
        content_object = wiki_ctype.get_object_for_this_type(pk=course.wiki.id)

        context['wiki_revisions'] = Revision.objects.filter(content_type=wiki_ctype, object_id=content_object.pk)

    context['documents'] = course.documents.all()
    context['can_upload_docs'] = current_user.has_perm('manage_resources', course)
    # Show documents/homework only if the user is registered and student/prof
    if current_user.is_student_of(course) or current_user.is_professor_of(course) or current_user.is_assistant_of(course):
        context['all_homework'] = course_homework_context(course, current_user)
        context['current_homework'] = [hw for hw in context['all_homework'] if hw['is_allowed']]
        if current_user.has_perm('assign_homework',course) or current_user.has_perm('grade_homework',course):
            context['homework_has_active'] = [hw['active_hw'] for hw in context['all_homework']].count(True) > 0
            context['homework_has_coming'] = [hw['coming_hw'] for hw in context['all_homework']].count(True) > 0
            context['homework_has_past'] = [hw['past_hw'] for hw in context['all_homework']].count(True) > 0

    context['teacher'] = course_teacher_dashboard(request, course, current_user)

    return context


def course_activities(request, course):
    user = request.user.juser
    # Needs discussion - This is getting all activities from the db and then doing the pagination
    activities_list = Activity.course_page_activities(course)
    activities_list = [a for a in activities_list if a.can_view(user)]

    activities_context = [activity_context(activity,user) for activity in activities_list]
    return paginated(request, activities_context, 20)



# loads NEW activities asynchronously, called with ajax
def new_course_activities(request,course):
    user = request.user.juser
    last_id = long(request.GET.get('last_id', 0))
    
    # Course activities 
    activities_list = Activity.course_page_activities(course).filter(id__gt=last_id)
    activities_list = [a for a in activities_list if a.can_view(user)]

    activities_context = [activity_context(activity,user) for activity in activities_list]
    return activities_context 


def activity_context(activity, current_user):
    activity_context = {
        "type": activity.get_type(),
        "activity": activity,
    }
    activity_type = activity_context["type"]
    activity_instance = activity.get_instance() # the most derived type


    if activity_type  == "ForumPostActivity":
        activity_context["post"] = forum_post_context(activity_instance.forum_post, current_user)
    elif activity_type == "ForumAnswerActivity":
        answer = activity_instance.forum_answer
        activity_context["answer"] = forum_answer_context(answer.post, answer, current_user)
    elif activity_type == "HomeworkActivity":
        activity_context['homework'] = homework_context(activity_instance.homework, current_user)
    elif activity_type == "ReviewActivity":
        activity_context["review"] = review_context(activity_instance.review, current_user)
    elif activity_type == "WikiActivity":
        activity_context['contribution'] = activity_instance.contribution
    return activity_context

# The page number is assumed to be in the GET parameters of the request.   
# objects_list should ideally be an unevaluated QuerySet
def paginated(request, objects_list, per_page):
    paginator = Paginator(objects_list, per_page) # 20 activities per page

    page = request.GET.get('page')
    try:
        objects = paginator.page(page).object_list
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        objects = paginator.page(1).object_list
    except EmptyPage:
        objects = []

    return objects