from mimetypes import guess_type
import hashlib
import string
import random
import datetime
import json
from guardian.shortcuts import assign_perm, remove_perm

from django.core.context_processors import csrf
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from django.core.mail import send_mail
from django.core.urlresolvers import reverse
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404, render_to_response
from django.http import Http404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.template import RequestContext
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST

from app.models import *
from app.course.context_processors import *
from app.forum.context_processors import *
from app.course.forms import *
from app.decorators import *


@require_GET
@login_required
def course_page(request, slug):
    course = get_object_or_404(Course, slug=slug)
    user = get_object_or_404(jUser, id=request.user.id)

    context = {
        "page": "course",
        'user_auth': request.user.juser
    }
    context.update(csrf(request))
    context = dict(context.items() + course_page_context(request, course).items())

    forum = course.forum
    context = dict(context.items() + forum_context(forum, user).items())

    available_pages = ['activity', 'info', 'connect', 'wiki', 'resources', 'teacher']
    if 'page' in request.GET and request.GET['page'] and \
        request.GET['page'] in available_pages:
            context['current_tab'] = request.GET['page']

    if 'filter' in request.GET and request.GET['filter']:
        tag = request.GET['filter']
        if tag in [vtag.name for vtag in forum.get_view_tags(user)]:
            context['current_filter'] = tag
        if 'current_tab' not in context:
            context['current_tab'] = 'connect'

    if 'post' in request.GET and request.GET['post']:
        post_id = int(request.GET['post'])
        posts = ForumPost.objects.filter(id=post_id)
        if len(posts) and posts[0].forum.id == forum.id:
            context['current_post'] = post_id
            if 'current_tab' not in context:
                context['current_tab'] = 'connect'

    if 'answer' in request.GET and request.GET['answer']:
        answer_id = int(request.GET['answer'])
        answers = ForumAnswer.objects.filter(id=answer_id)
        if len(answers) and answers[0].post.forum.id == forum.id:
            context['current_post'] = answers[0].post.id
            context['current_answer'] = answer_id
            if 'current_tab' not in context:
                context['current_tab'] = 'connect'


    if 'review_course_tab' in request.GET and request.GET['review_course_tab']:
        context['review_course_tab'] = True

    available_teacher_pages = ['registered', 'pending', 'upload', 'homework', 'forum', 'details', 'assistants']
    if 'teacher_page' in request.GET and request.GET['teacher_page'] and \
        request.GET['teacher_page'] in available_teacher_pages:
            context['current_teacher_tab'] = request.GET['teacher_page']
            if 'current_tab' not in context:
                context['current_tab'] = 'teacher'

    if 'current_tab' not in context and not len(context['activities']):
        context['current_tab'] = 'info'

    return render(request, "pages/course.html", context)


@require_GET
@login_required
def get_course_image(request, slug):
    course = get_object_or_404(Course, slug=slug)
    if not course.image:
        raise Http404

    content_type = guess_type(course.image.name)
    return HttpResponse(course.image, mimetype=content_type)


@require_POST
@require_active_user
@login_required
def submit_review(request, slug):

    form = SubmitCommentForm(request.POST)
    if not form.is_valid():
        raise Http404

    user = get_object_or_404(jUser, id=request.user.id)

    course = form.cleaned_data['course']

    comment_text = form.cleaned_data['comment']
    comment = Review(course=course, review=comment_text, posted_by=user,
                     anonymous=form.cleaned_data['anonymous'])
    comment.save()
    comment.upvoted_by.add(user)

    context = {
        'course': course,
        'comment': review_context(comment, user)
    }
    response_data = {}
    response_data['html'] = render_to_string("objects/course/review.html", RequestContext(request, context))
    return HttpResponse(json.dumps(response_data), content_type="application/json")


@require_POST
@require_active_user
@login_required
def rate_course(request, slug):
    user = get_object_or_404(jUser, id=request.user.id)

    form = RateCourseForm(request.POST)
    if not form.is_valid():
        raise Http404

    course = get_object_or_404(Course, slug=slug)
    course_form = form.cleaned_data['course']
    if course.id != course_form.id:
        raise Http404

    rating_value = form.cleaned_data['rating_value']
    rating_type = form.cleaned_data['rating_type']

    if rating_type != PROFESSOR_R:
        ratings = Rating.objects.filter(user=user, course=course, rating_type=rating_type)
        if len(ratings) == 0:
            rating = Rating(user=user, course=course, rating=rating_value, rating_type=rating_type)
            rating.save()
        else:
            rating = ratings[0]
            rating.rating = rating_value
            rating.save()
    else:
        prof = form.cleaned_data['prof']
        ratings = Rating.objects.filter(user=user, course=course, rating_type=rating_type, professor=prof)
        if len(ratings) == 0:
            rating = Rating(user=user, course=course, rating=rating_value, rating_type=rating_type, professor=prof)
            rating.save()
        else:
            rating = ratings[0]
            rating.rating = rating_value
            rating.save()


    context = {
        'course': course,
        'ratings': course_ratings_context(course, user)
    }
    response_data = {}
    response_data['ratings'] = render_to_string("objects/course/ratings.html", RequestContext(request, context))
    return HttpResponse(json.dumps(response_data), content_type="application/json")

@require_GET
@require_active_user
@login_required
def view_document(request, slug, document_id):
    user = get_object_or_404(jUser, id=request.user.id)
    course = get_object_or_404(Course, slug=slug)
    document = get_object_or_404(CourseDocument, id=document_id)

    if not user.is_student_of(course) and not user.is_professor_of(course) and user.is_admin_of(course):
        raise Http404

    if not document.course == course:
        raise Http404

    # In development
    if settings.DEBUG:
        content_type = guess_type(document.document.name)
        return HttpResponse(document.document, content_type=content_type)

    conn = boto.connect_s3()
    bucket = conn.get_bucket(settings.AWS_STORAGE_BUCKET_NAME)
    key = bucket.get_key(document.name)

    doc_file = NamedTemporaryFile(delete=True)
    key.get_file(doc_file)

    content_type = guess_type(document.name)
    return HttpResponse(doc_file, content_type=content_type)

@require_POST
@require_active_user
@login_required
def submit_document(request, slug):
    context = {}

    user = get_object_or_404(jUser, id=request.user.id)
    course = get_object_or_404(Course, slug=slug)

    form = SubmitDocumentForm(request.POST, request.FILES)

    if not form.is_valid():
        raise Http404

    if not user.has_perm('manage_resources', course):
        raise Http404

    docfile = form.cleaned_data['document']
    course_document = CourseDocument(document=docfile, name=form.cleaned_data['name'],
                                     description=form.cleaned_data['description'], course=form.cleaned_data['course'], 
                                     submitter=user, course_topic=form.cleaned_data["topic"])
    course_document.save()

    return redirect( reverse('course_page', args=(course.slug, )) + "?page=resources" )


@require_POST
@require_active_user
@login_required
def resubmit_document(request, slug):
    context = {}

    user = get_object_or_404(jUser, id=request.user.id)
    course = get_object_or_404(Course, slug=slug)

    form = ResubmitDocumentForm(request.POST, request.FILES)

    if not form.is_valid():
        raise Http404

    if not user.has_perm('manage_resources', course):
        raise Http404

    docfile = form.cleaned_data['document']
    document = form.cleaned_data['doc_obj']
    document.document = docfile
    document.save()

    return redirect( reverse('course_page', args=(course.slug, )) + "?page=resources" )


@require_POST
@require_active_user
@login_required
def submit_homework(request, slug):
    context = {}

    user = get_object_or_404(jUser, id=request.user.id)

    form = SubmitHomeworkForm(request.POST, request.FILES)

    if not form.is_valid():
        raise Http404

    course = form.cleaned_data['course']
    registration_status = course.get_registration_status(user)
    if registration_status != COURSE_REGISTRATION_REGISTERED:
        raise Http404

    homework_request = form.cleaned_data['homework_request']

    for idx in range(HOMEWORK_MIN_FILES, homework_request.number_files + 1):
        docfile = form.cleaned_data.get('document' + str(idx))
        if docfile:
            # Delete previous
            previous_homework = CourseHomeworkSubmission.objects.filter(submitter=user, homework_request=homework_request, file_number=idx)
            for prev_hw in previous_homework:
                prev_hw.delete()
            # Create new
            course_homework = CourseHomeworkSubmission(document=docfile, course=form.cleaned_data['course'],
                                                       submitter=user, homework_request=homework_request, file_number=idx)
            course_homework.save()

    return redirect( reverse('course_page', args=(course.slug, )) + "?page=resources" )


@require_POST
@require_active_user
@login_required
def submit_homework_request(request, slug):
    context = {}

    user = get_object_or_404(jUser, id=request.user.id)
    course = get_object_or_404(Course, slug=slug)

    form = SubmitHomeworkRequestForm(request.POST, request.FILES)
    if not form.is_valid():
        raise Http404

    if not course == form.cleaned_data['course']:
        raise Http404

    if not user.has_perm('assign_homework', course):
        raise Http404

    local_timezone = timezone.get_current_timezone()
    if timezone.is_naive(form.cleaned_data['start']):
        form.cleaned_data['start'] = timezone.make_aware(form.cleaned_data['start'], local_timezone)
    if timezone.is_naive(form.cleaned_data['deadline']):
        form.cleaned_data['deadline'] = timezone.make_aware(form.cleaned_data['deadline'], local_timezone) 
    start_time = timezone.localtime(form.cleaned_data['start'], pytz.utc)
    end_time = timezone.localtime(form.cleaned_data['deadline'], pytz.utc)

    deadline = Deadline(start=start_time, end=end_time)
    deadline.save()
    homework_request = CourseHomeworkRequest(name=form.cleaned_data['name'], description=form.cleaned_data['description'],
                                             course=form.cleaned_data['course'], submitter=user, 
                                             deadline=deadline, course_topic=form.cleaned_data["topic"],
                                             number_files=form.cleaned_data['nr_files'])

    docfile = form.cleaned_data['document']
    if docfile:
        course_document = CourseDocument(document=docfile, name=form.cleaned_data['name'],
                                     description=form.cleaned_data['description'], course=form.cleaned_data['course'], 
                                     submitter=user, course_topic=form.cleaned_data["topic"])
        course_document.save()
        homework_request.document = course_document
    homework_request.save()

    return redirect( reverse('course_page', args=(course.slug, )) + "?page=resources" )


@require_POST
@require_active_user
@login_required
def edit_homework_request(request, slug):
    context = {}

    user = get_object_or_404(jUser, id=request.user.id)
    course = get_object_or_404(Course, slug=slug)

    form = EditHomeworkRequestForm(request.POST, request.FILES)
    if not form.is_valid():
        raise Http404

    if not course == form.cleaned_data['course']:
        raise Http404

    if not user.has_perm('assign_homework', course):
        raise Http404

    local_timezone = timezone.get_current_timezone()
    if timezone.is_naive(form.cleaned_data['start']):
        form.cleaned_data['start'] = timezone.make_aware(form.cleaned_data['start'], local_timezone)
    if timezone.is_naive(form.cleaned_data['deadline']):
        form.cleaned_data['deadline'] = timezone.make_aware(form.cleaned_data['deadline'], local_timezone) 
    start_time = timezone.localtime(form.cleaned_data['start'], pytz.utc)
    end_time = timezone.localtime(form.cleaned_data['deadline'], pytz.utc)

    homework_request = form.cleaned_data['homework_request']
    deadline = homework_request.deadline
    deadline.start = start_time
    deadline.end = end_time
    deadline.save()

    homework_request.name=form.cleaned_data['name']
    homework_request.description=form.cleaned_data['description']
    homework_request.course_topic=form.cleaned_data["topic"]
    homework_request.save()

    get_params = "?homework=" + str(homework_request.id)
    return redirect( reverse('homework_dashboard', args=(course.slug, )) + get_params )


@require_POST
@require_active_user
@login_required
def submit_homework_grades(request, slug):

    user = get_object_or_404(jUser, id=request.user.id)
    course = get_object_or_404(Course, slug=slug)
    if not user.has_perm('grade_homework', course):
        raise Http404

    form = SubmitHomeworkGradesForm(request.POST)
    if not form.is_valid():
        raise Http404

    hw = form.cleaned_data['homework_request']
    if hw.course != course:
        raise Http404

    students = course.students.all()
    if form.cleaned_data.get('save'):
        for st in students:
            for idx in range(1, hw.number_files + 1):
                field_name = st.username + "-" + str(idx)
                grade = form.cleaned_data.get(field_name)
                if grade:
                    hw_grades = CourseHomeworkGrade.objects.filter(student=st, file_number=idx, homework_request=hw)
                    if not hw_grades:
                        grade = CourseHomeworkGrade.objects.create(student=st, file_number=idx, homework_request=hw,
                                                                   submitter=user, is_published=False, grade=grade)
                        subms = CourseHomeworkSubmission.objects.filter(submitter=st, file_number=idx, homework_request=hw)
                        if subms:
                            grade.submission = subms[0]
                            grade.save()
                    else:
                        hw_grade = hw_grades[0]
                        hw_grade.grade = grade
                        hw_grade.submitter = user
                        hw_grade.save()
                else:
                    hw_grades = CourseHomeworkGrade.objects.filter(student=st, file_number=idx, homework_request=hw)
                    if hw_grades:
                        hw_grades[0].delete()


    if form.cleaned_data.get('publish'):
        # Check if everyone has a grade
        can_publish = True
        for st in students:
            for idx in range(1, hw.number_files + 1):
                subms = CourseHomeworkSubmission.objects.filter(submitter=st, file_number=idx, homework_request=hw)
                if subms and not hasattr(subms[0], 'grade'):
                    can_publish = False
                    break
            if not can_publish:
                break
        if can_publish:
            # Publish the results
            for st in students:
                for idx in range(1, hw.number_files + 1):
                    field_name = st.username + "-" + str(idx)
                    hw_grades = CourseHomeworkGrade.objects.filter(student=st, file_number=idx, homework_request=hw)
                    if hw_grades:
                        hw_grades[0].is_published = True
                        hw_grades[0].save()
                    else:
                        CourseHomeworkGrade.objects.create(student=st, file_number=idx, homework_request=hw,
                                                        submitter=user, is_published=True, grade=0.0)
            hw.is_published = True
            hw.save()
        else:
            raise Http404


    return redirect( reverse('homework_dashboard', args=(course.slug, )) )

@require_GET
@require_active_user
@login_required
def homework_dashboard(request, slug):
    context = {
        'page': 'homework_dashboard'
    }

    user = get_object_or_404(jUser, id=request.user.id)
    course = get_object_or_404(Course, slug=slug)
    if not user.has_perm('grade_homework', course):
        raise Http404

    context = dict(context.items() + homework_dashboard_context(request, course, user).items())
    context['course'] = course

    if 'homework' in request.GET and request.GET['homework']:
        for hw in context['homework_requests']:
            if str(hw['homework'].id) == request.GET['homework']:
                context['current_homework'] = int(request.GET['homework'])

    return render(request, 'pages/course/homework_dashboard.html', context)


@require_POST
@require_active_user
@login_required
def vote_review(request, slug):
    context = {}

    user = get_object_or_404(jUser, id=request.user.id)

    form = VoteReviewForm(request.POST)

    if not form.is_valid():
        raise Http404

    review = form.cleaned_data['review']

    if form.cleaned_data['vote_type'] == "upvote":
        if not review.upvoted_by.filter(username=user.username).count():
            review.upvoted_by.add(user)
        else:
            review.upvoted_by.remove(user)
    if form.cleaned_data['vote_type'] == "downvote":
        if not review.downvoted_by.filter(username=user.username).count():
            review.downvoted_by.add(user)

    context = {
        'course': review.course,
        'comment': review_context(review, user)
    }
    response_data = {}
    response_data['html'] = render_to_string("objects/course/upvote_review.html", RequestContext(request, context))
    return HttpResponse(json.dumps(response_data), content_type="application/json")


@require_active_user
@login_required
def register_course(request, slug):
    context = {
        "page": "register_course"
    }
    course = get_object_or_404(Course, slug=slug)
    user = get_object_or_404(jUser, id=request.user.id)

    context.update(csrf(request))
    registration_deadline = course.get_registration_deadline()
    registration_status = course.get_registration_status(user)
    registration_open = registration_deadline.is_open() if registration_deadline is not None else False

    if user.user_type == USER_TYPE_STUDENT:
        if registration_open:
            if registration_status == COURSE_REGISTRATION_OPEN:
                course_registration = StudentCourseRegistration(student=user,
                                                                course=course,
                                                                is_approved=False)
                course_registration.save()
                return HttpResponse("OK", context)
            elif registration_status in [COURSE_REGISTRATION_PENDING, COURSE_REGISTRATION_REGISTERED]:
                return HttpResponse("You have already registered for this course.", context)
            elif registration_status == COURSE_REGISTRATION_NOT_ALLOWED:
                return HttpResponse("You are not allowed to register for this course")
        else:
            return HttpResponse("Course registration period is not open.")
    elif user.user_type == USER_TYPE_PROFESSOR:
        if registration_status == COURSE_REGISTRATION_OPEN:
                course_registration = ProfessorCourseRegistration(professor=user,
                                                                  course=course,
                                                                  is_approved=False)
                course_registration.save()
                return HttpResponse("OK", context)
        elif registration_status in [COURSE_REGISTRATION_PENDING, COURSE_REGISTRATION_REGISTERED]:
            return HttpResponse("You have already registered for this course.", context)
        elif registration_status == COURSE_REGISTRATION_NOT_ALLOWED:
            return HttpResponse("You are not allowed to register for this course.")
    else:
        return HttpResponse("You are not allowed to register for this course.")


@require_POST
@require_active_user
@login_required
def send_mass_email(request, slug):
    course = get_object_or_404(Course, slug=slug)
    context = {
        'page': 'send_mass_email',
        'user_auth': request.user
    }
    context.update(csrf(request))

    # Make sure the logged in user is allowed to approve these registrations
    user = request.user
    if not user.has_perm('mail_students', course):
        return HttpResponse("You don't have permission to perform this action")
    subject = request.POST['subject']
    body = request.POST['email']
    to = []
    sender = "%s %s <%s>" % (user.first_name, user.last_name, user.email)
    for key, val in request.POST.items():
        if 'user' in key:
            _, user_id = key.split('-')
            users = jUser.objects.filter(id=user_id)
            if users is not None and val:  # if user exists (users is not None) and checkbox was checked (val)
                email = users[0].email
                to.append(email)

    if len(to) > 0:
        send_mail(subject, body, sender, to, fail_silently=False)
        return HttpResponse("OK")
    else:
        return HttpResponse("Please select at least one recepient.")

@require_POST
@require_active_user
@login_required
def update_info(request, slug):
    course = get_object_or_404(Course, slug=slug)
    user = get_object_or_404(jUser, id=request.user.id)

    if not user.has_perm('manage_info', course):
        raise Http404

    form = UpdateInfoForm(request.POST)

    if not form.is_valid():
        raise Http404

    if 'description' in form.cleaned_data and form.cleaned_data['description']:
        course.description = form.cleaned_data['description']
    if 'additional_info' in form.cleaned_data and form.cleaned_data['additional_info']:
        course.additional_info = form.cleaned_data['additional_info']
    if 'abbreviation' in form.cleaned_data and form.cleaned_data['abbreviation']:
        course.abbreviation = form.cleaned_data['abbreviation']
    course.save()

    return redirect( reverse('course_page', args=(course.slug, )) + "?teacher_page=details" )

@require_POST
@require_active_user
@login_required
def update_syllabus(request, slug):
    course = get_object_or_404(Course, slug=slug)
    user = get_object_or_404(jUser, id=request.user.id)

    if not user.has_perm('manage_info', course):
        raise Http404

    form = UpdateSyllabusForm(request.POST)

    if not form.is_valid():
        raise Http404

    if 'course_topic' in form.cleaned_data and form.cleaned_data['course_topic']:
        topic = form.cleaned_data['course_topic']
        topic.name = form.cleaned_data['entry_name']
        topic.description = form.cleaned_data['entry_description']
        topic.save()
    else:
        CourseTopic.objects.create(name=form.cleaned_data['entry_name'], description=form.cleaned_data['entry_description'], course=course)

    return redirect( reverse('course_page', args=(course.slug, )) + "?teacher_page=details" )


@require_POST
@require_active_user
@login_required
def delete_syllabus_entry(request, slug):
    course = get_object_or_404(Course, slug=slug)
    user = get_object_or_404(jUser, id=request.user.id)

    if not user.has_perm('manage_info', course):
        raise Http404

    form = DeleteSyllabusEntryForm(request.POST)

    if not form.is_valid():
        raise Http404

    form.cleaned_data['course_topic'].delete()

    return redirect( reverse('course_page', args=(course.slug, )) + "?teacher_page=details" )

### ACTIVITIES AJAX URLS #####

@login_required
def load_course_activities(request, slug):
    course = get_object_or_404(Course, slug=slug)
    user = request.user.juser
    activities = course_activities(request,course)
    if len(activities) == 0:
        return HttpResponse(json.dumps({
                'status': "OK",
                'html': ""
            }))
    context = { "activities" : activities, "user_auth": user }
    context.update(csrf(request))
    html = render_to_string('objects/dashboard/activity_timeline.html', context )
    data = {
        'status': "OK",
        'html': html
    }

    return HttpResponse(json.dumps(data))

@login_required
def load_new_course_activities(request,slug):
    course = get_object_or_404(Course, slug=slug)
    user = request.user.juser
    activities = new_course_activities(request,course)
    context = { "activities" : activities, "user_auth": user }
    context.update(csrf(request))

    html = render_to_string('objects/dashboard/activity_timeline.html', context )
    data = {
        'status': "OK",
        'html': html,
    }
    if activities:
        data['new_last_id'] = activities[0]['activity'].id

    return HttpResponse(json.dumps(data))

@login_required
@require_POST
@require_professor
@require_active_user
def add_new_ta(request,slug):
    course = get_object_or_404(Course, slug=slug)
    user = request.user.juser
    context = {
        'page': 'course_page',
        'user_auth': user,
        'course': course,
    }
    context.update(csrf(request))

    form = NewTAForm(request.POST)
    if not form.is_valid():
        raise Http404

    if not user.is_professor_of(course):
        raise Http404

    # Default permissions
    default_permissions = ['mail_students', 'assign_homework', 'manage_resources', 'grade_homework','manage_forum','manage_info']

    user_email = form.cleaned_data['user']
    tas = jUser.objects.filter(email=user_email)
    if len(tas) > 0:
        ta = tas[0]
        if course.teaching_assistants.filter(email=user_email).exists():
            return_dict = {
                'status': "Warning",
                'message': "%s %s is already a TA" % (ta.first_name, ta.last_name),
            }
            return HttpResponse(json.dumps(return_dict))
        else:
            course.teaching_assistants.add(ta)
        for perm in default_permissions:
            assign_perm(perm,ta,course)

        ta_context = {'user': ta, 'permissions': []}
        for perm in Course._meta.permissions:
            ta_context['permissions'].append({
                'name': perm[0],
                'description': perm[1],
                'owned': ta.has_perm(perm[0], course)
            })
        context['ta'] = ta_context

        html = render_to_string('objects/course/management/ta_item.html', context)

        return_dict = {
            'status': "OK",
            'html': html,
        }
        return HttpResponse(json.dumps(return_dict))

    else:
        return_dict = {
            'status': "Error",
            'message': "User not found"
        }
        return HttpResponse(json.dumps(return_dict))

@login_required
@require_POST
@require_professor
@require_active_user
def change_ta_permissions(request,slug):
    context = {
        'page': 'course_page'
    }
    context.update(csrf(request))

    user = request.user.juser
    course = get_object_or_404(Course,slug=slug)


    if not user.is_professor_of(course):
        raise Http404

    form = TAPermissionsForm(request.POST)
    if not form.is_valid():
        raise Http404

    ta = get_object_or_404(jUser, id = form.cleaned_data['user_id'])

    for perm in Course._meta.permissions:
        permission = perm[0]
        print permission
        print str(form.cleaned_data[permission])
        if form.cleaned_data[permission]:
            assign_perm(permission, ta, course)
        else:
            remove_perm(permission, ta, course)

    return_dict = {
        "status": "OK",
        "message": "Saved"
    }
    return HttpResponse(json.dumps(return_dict))

@login_required
@require_POST
@require_professor
@require_active_user
def remove_ta(request,slug):
    course = get_object_or_404(Course, slug=slug)
    current_user = request.user.juser

    if not current_user.is_professor_of(course):
        raise Http404

    form = RemoveTAForm(request.POST)
    if not form.is_valid():
        raise Http404

    ta_id = form.cleaned_data['user_id']

    tas = jUser.objects.filter(id=ta_id)
    if len(tas) != 1:
        return_dict = {
            'status': "Error",
            'message': "User not found"
        }
        return HttpResponse(json.dumps(return_dict))

    ta = tas[0]
    if not course.teaching_assistants.filter(id=ta.id).exists():
        return_dict = {
            'status': "Error",
            'message': "User is not a TA of %s" % course.name
        }
        return HttpResponse(json.dumps(return_dict))


    # All is good
    # Drop all permissions of the ex-TA
    for perm in Course._meta.permissions:
        remove_perm(perm[0], ta, course)
    # Remove the ex-TA from the course's teaching assistants
    course.teaching_assistants.remove(ta)
    return_dict = {
        'status': "OK",
        'ta_id': ta.id
    }

    return HttpResponse(json.dumps(return_dict))
