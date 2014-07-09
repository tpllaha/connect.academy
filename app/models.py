from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.conf import settings 
from datetime import * #datetime
import pytz # timezones





###########################################################################
####################### User Related Models ###############################
###########################################################################


USER_TYPE_STUDENT = 0
USER_TYPE_PROFESSOR = 1
USER_TYPE_ADMIN = 2 # The administator of at least 1 category, who is not a professor

USER_TYPES = (
    (USER_TYPE_STUDENT, "student"),
    (USER_TYPE_PROFESSOR, "professor"),
    (USER_TYPE_ADMIN, "admin")
)

# Inheriting from Base Class 'User'
class jUser(User):

    user_type = models.IntegerField(choices=USER_TYPES, default=USER_TYPE_STUDENT)
    university = models.ForeignKey('University',null = True) 
    
    # For professors only 
    # True if they have been confirmed to be professors)
    is_confirmed = models.NullBooleanField(default = False)
    # Courses the user is enrolled to
    courses_enrolled = models.ManyToManyField('Course', related_name='students', 
                                               through = 'StudentCourseRegistration')

    # courses the user is managing (i.e: if they're professors)
    courses_managed = models.ManyToManyField('Course', related_name='professors',
                                              through = 'ProfessorCourseRegistration')

    # may turn out useful - this might also need approval,
    # so we may have to create another table to handle the ManyToMany relation
    majors = models.ManyToManyField('Major', related_name = 'students')

    # !! 
    # Relations declared in other models define the following:
    #    categories_managed: (<juser>.categories_managed.all() returns all categories that have <juser> 
    #    as an admin)
    #    upvoted: (<juser>.upvoted.all() returns all comments that <juser> upvoted)
    #    downvoted: (<juser>.upvoted.all() returns all comments that <juser> downvoted)

    def __unicode__(self):
        return str(self.username)

    def is_professor_of(self, course):
        registration = ProfessorCourseRegistration.objects.filter(professor=self, course=course)
        return registration and registration[0].is_approved


class StudentCourseRegistration(models.Model):
    student = models.ForeignKey('jUser')
    course = models.ForeignKey('Course')
    is_approved = models.BooleanField(default = False) # True if registration is approved

    def __unicode__(self):
        return str(self.student)

class ProfessorCourseRegistration(models.Model):
    professor = models.ForeignKey('jUser')
    course = models.ForeignKey('Course')
    is_approved = models.BooleanField(default = False) # True if registration is approved

    def __unicode__(self):
        return str(self.professor)









###########################################################################
################# University/Course Related Models ########################
###########################################################################

# Course types
COURSE_TYPE_UG = 0
COURSE_TYPE_GRAD = 1
COURSE_TYPES = (
    (COURSE_TYPE_UG,"Undergraduate"),
    (COURSE_TYPE_GRAD, "Graduate")
)

# Registration statuses
COURSE_REGISTRATION_OPEN = 0 # The user can register for this course
COURSE_REGISTRATION_PENDING = 1 # Registration for this course is pending approval
COURSE_REGISTRATION_REGISTERED = 2 # User is registered for this course
COURSE_REGISTRATION_NOT_ALLOWED = 3 # User is not allowed to register for this course

REGISTRATION_STATUSES = (
    (COURSE_REGISTRATION_OPEN, "Open"),
    (COURSE_REGISTRATION_PENDING, "Pending"),
    (COURSE_REGISTRATION_REGISTERED, "Registered"),
    (COURSE_REGISTRATION_NOT_ALLOWED, "Not_Allowed")
)

class Major(models.Model):
    # We could use this later to add more functionality, 
    # we can add major requirements, courses etc.
    name = models.CharField(max_length = 200)
    abbreviation = models.CharField(max_length=10, blank = True, null=True)
    # !!
    # Relations declared in other models define the following:
    #    courses: (<major>.courses.all() returns all courses of <major>) 
    #    students: (<major>.students.all() returns all students of <major>)

    def __unicode__(self):
        return str(self.name)

class Course(models.Model):
    course_id = models.IntegerField()
    name = models.CharField(max_length=200)
    course_type = models.IntegerField(choices=COURSE_TYPES, default = COURSE_TYPE_UG)
    credits = models.FloatField()
    description = models.CharField(max_length=5000, blank=True, null = True)
    additional_info = models.CharField(max_length=5000, blank=True, null=True)
    abbreviation = models.CharField(max_length=50, blank=True, null=True)
    slug = models.SlugField(max_length=200)
    image = models.ImageField(upload_to='courses')
    university = models.ForeignKey('University', related_name = 'courses')
    category = models.ForeignKey('Category', null=True, default=None, related_name = 'courses')
    tags = models.ManyToManyField('Tag',related_name='courses')
    majors = models.ManyToManyField('Major', related_name='courses')
    prerequisites = models.ManyToManyField('self',related_name='next_courses')
    # !!
    # Relations declared in other models define the following:
    #   professors (<course>.professor.all() returns all professors of <course>)
    #   students    (<course>.students.all()    returns all students    of <course>)
    #   next_courses (<course>.next_courses.all() returns all courses that have
    #                 <course> as a prerequisite)
    #   forumcourse_set (<course>.forumcourse_set.all() returns all forums of the <course>)
    

    # gets the registration status of this course for the given user
    # Registration status is one of the following:
    #   COURSE_REGISTRATION_OPEN       (0): The student can register for the course
    #   COURSE_REGISTRATION_PENDING     (1): Registration is pending approval
    #   COURSE_REGISTRATION_REGISTERED    (2): User is registered for the course
    #   COURSE_REGISTRATION_NOT_ALLOWED     (3): User is not allowed to register for the course

    def get_registration_status(self,user):
        registration = None
        if user.user_type == USER_TYPE_STUDENT:
            try:
                registration = StudentCourseRegistration.objects.get(student=user, course = self)
            except exception:
                pass
        elif user.user_type == USER_TYPE_PROFESSOR:
            try:
                registration = ProfessorCourseRegistration.objects.get(professor = user, course = self)
            except Exception:
                pass
        else:
            return COURSE_REGISTRATION_NOT_ALLOWED # Not a user, not a professor

        if registration is None:
            if user.university == self.university and user.is_active:
                return COURSE_REGISTRATION_OPEN
            else:
                return COURSE_REGISTRATION_NOT_ALLOWED
        else:
            if registration.is_approved:
                return COURSE_REGISTRATION_REGISTERED
            else:
                return COURSE_REGISTRATION_PENDING

        return None # This line will never be reached

        

    def get_cr_deadline(self):
        category = self.category
        if category is not None:
            return category.get_cr_deadline()
        else:
            return None

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super(Course, self).save(*args, **kwargs)

    def __unicode__(self):
        return str(self.name)



class Tag(models.Model):
    # Besides name, we might need to add more fancy things to tags (we can group them etc)
    name = models.CharField(max_length = 100)
    # !!
    # Relations declared in other models define the following:
    #   courses (<tag>.courses.all() returns all courses of that have <tag>)

    def __unicode__(self):
        return str(self.name)



class University(models.Model):
    name = models.CharField(max_length=150)
    # Relations declared in other models define the following:
    #   domains (<university>.domains.all() returns all domains of a university)
    #   courses (<university>.courses.all() returns all courses of a university)

    def __unicode__(self):
        return str(self.name)



class Category(models.Model):
    parent = models.ForeignKey('self',null = True, related_name = 'children') # Parent category
    level = models.IntegerField(null=True) # The level in which the category is positioned in the tree
    name = models.CharField(max_length = 150)
    abbreviation = models.CharField(max_length = 10)
    admins = models.ManyToManyField('jUser', related_name = 'categories_managed')
    #course registration deadline
    cr_deadline = models.ForeignKey('CourseRegistrationDeadline', related_name = 'category',null=True)
    # !!
    # Relations declared in other models define the following:
    #   courses (<category>.courses.all() returns all courses that are direct children of <category>)
    #   children (<category>.children.all() returns all child categories of <category>)    
    def get_admins(self):
        # Gets the "closest" administrators of a category. 
        admins = self.admins.all()
        if len(admins) > 0:
            return admins
        elif self.parent != None: # if not root
            return self.parent.get_admins()
        else:
            return None

    def get_all_admins(self):
        # get all people with administrator rights of this category
        # (i.e: including admins of parent categories)
        admins = list(self.admins.all())
        if self.parent != None:
            admins += self.parent.get_all_admins()
        return admins


    def get_all_courses(self):
        # Gets all the courses that are descendants of this category
        allcourses = list(self.courses.all())
        children = Category.objects.filter(parent__id = self.id)
        for child in children:
            allcourses += list(child.get_all_courses())

        return allcourses

    # finds the course registration deadline for this category (by climbing up to the root of the tree
    # until a category with a deadline is found)
    def get_cr_deadline(self):
        if self.cr_deadline is not None:
            return self.cr_deadline
        elif self.parent is not None:
            return self.parent.get_cr_deadline()
        else:
            return None

    # gets the subtree that has this category in the root. The tree is returned as a dictionary,
    # such that when converted to JSON, it follows the specifications to build a Spacetree with 
    # Infoviz (the javascript visualization tool)
    def get_subtree(self):
        tree = {
            'id' : "category-" + str(self.id),
            'name' : self.name,
            'data' : {
                'type': 'category', # category or course
                'admins': []
            },
            'children' : []
        }
        admins = self.get_all_admins()
        if admins is not None:
            for admin in admins:
                tree['data']['admins'].append({
                    'first_name': admin.first_name,
                    'last_name': admin.last_name,
                    'username': admin.username,
                    'id': admin.id,
                    'own_admin': admin in self.admins.all()

                })


        children = self.children.all()
        courses = self.courses.all()

        for child in children:
            subtree = child.get_subtree()
            tree['children'].append(subtree)

        for course in courses: 
            course_dict = {
                'id': "course-" + str(course.id),
                'name' : course.name,
                'data' : {
                    'type' : 'course',
                    'professors': []
                },
                'children' : []
            }
            for prof in course.professors.all():
                course_dict['data']['professors'].append({
                    'first_name': prof.first_name,
                    'last_name': prof.last_name,
                    'username': prof.username,
                    'id': prof.id
                })
                tree['children'].append(course_dict)

        return tree

        # returns all categories that are descendats of this one together with this category
        # this is useful to list the categories in the admin page
    def get_descendants(self):
        descendants = list(self.children.all())
        for cat in descendants:
            descendants2 = list(cat.get_descendants())
            for desc in descendants2:
                if not desc in descendants:
                    descendants.append(desc)
        return descendants


    def __unicode__(self):
        return str(self.name)

class Domain(models.Model):
    # University Domain
    name = models.CharField(max_length=200,unique = True)
    university = models.ForeignKey('University', related_name='domains')

    def __unicode__(self):
        return str(self.name)


class WikiPage(models.Model):
    name = models.CharField(max_length=50,primary_key=True)
    content = models.TextField(blank=True)

    def __unicode__(self):
        return str(self.name)


class Deadline(models.Model):
    start = models.DateTimeField(default=pytz.utc.localize(datetime.now()))
    end = models.DateTimeField()

class CourseRegistrationDeadline(Deadline):
    # need to change the field above to non-nullable.
    def is_open(self):
        now = pytz.utc.localize(datetime.now())  #using utc as reference time zone
        if now >= self.start and now < self.end:
            return True
        else:
            return False
    # !!
    # Relations declared in other models define the following:
    # category: <courseregistrationdeadline>.category is the category this registration deadline is for




###########################################################################
####################### Reviews, Ratings, Documents, Homework #############
###########################################################################

RATING_MIN = 1
RATING_MAX = 5
OVERALL_R = 'ALL'
WORKLOAD_R = 'WKL'
DIFFICULTY_R = 'DIF'
PROFESSOR_R = 'PRF'
RATING_TYPES = (
    (OVERALL_R, 'Overall'),
    (WORKLOAD_R, 'Workload'),
    (DIFFICULTY_R, 'Difficulty'),
    (PROFESSOR_R, 'Professor')
)


class Rating(models.Model):
    user = models.ForeignKey('jUser', related_name='rated')
    course = models.ForeignKey('Course')
    rating = models.FloatField()
    rating_type = models.CharField( max_length=3,
                                    choices=RATING_TYPES,
                                    default=OVERALL_R)
    professor = models.ForeignKey('jUser', related_name='been_rated', null=True, blank=True)

    def __unicode__(self):
        return str(self.rating)

class Review(models.Model):
    course = models.ForeignKey('Course')
    review = models.CharField(max_length=5000)
    datetime = models.DateTimeField(auto_now=True)

    posted_by = models.ForeignKey('jUser', related_name='reviews_posted')
    anonymous = models.BooleanField(default=False)

    upvoted_by = models.ManyToManyField('jUser', related_name='review_upvoted')
    downvoted_by = models.ManyToManyField('jUser', related_name='review_downvoted')

    def __unicode__(self):
        return str(self.review)

class CourseDocument(models.Model):
    name = models.CharField(max_length=200)
    description = models.CharField(max_length=1000, null=True, blank=True)
    document = models.FileField(upload_to='course/documents/')

    course = models.ForeignKey('Course')
    submitter = models.ForeignKey('jUser')
    submit_time = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return str(self.name)

class CourseHomeworkRequest(models.Model):
    name = models.CharField(max_length=200)
    description = models.CharField(max_length=1000, null=True, blank=True)
    deadline = models.ForeignKey('Deadline')

    course = models.ForeignKey('Course')
    submitter = models.ForeignKey('jUser')

    def delete(self, *args, **kwargs):
        deadline = self.deadline
        super(CourseHomeworkRequest, self).save(*args, **kwargs)
        deadline.delete()

    def __unicode__(self):
        return str(self.name)

class CourseHomeworkSubmission(models.Model):
    homework_request = models.ForeignKey('CourseHomeworkRequest')
    document = models.FileField(upload_to='course/homework/')

    course = models.ForeignKey('Course')
    submitter = models.ForeignKey('jUser')
    submit_time = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=200)

    def save(self, *args, **kwargs):
        self.name = slugify(self.submitter.first_name + "-" + self.submitter.last_name + "-" + self.homework_request.name)
        super(CourseHomeworkSubmission, self).save(*args, **kwargs)

    def __unicode__(self):
        return str(self.name)

###########################################################################
############################ Forums, Wikis ################################
###########################################################################


# Course types
FORUM_TYPE_COURSE = 0
FORUM_TYPE_TOPIC = 1
FORUM_TYPE_HOMEWORK = 2
FORUM_TYPES = (
    (FORUM_TYPE_COURSE,"Course"),
    (FORUM_TYPE_TOPIC, "Topic"),
    (FORUM_TYPE_HOMEWORK, "Homework")
)

class Forum(models.Model):
    forum_type = models.IntegerField(choices=FORUM_TYPES, default=FORUM_TYPE_COURSE)

    def __unicode__(self):
        return dict(FORUM_TYPES)[self.forum_type]

class ForumCourse(Forum):
    course = models.ForeignKey('Course')

    def __unicode__(self):
        return str(self.course)

class ForumHomework(Forum):
    homework_request = models.ForeignKey('CourseHomeworkRequest')

    def __unicode__(self):
        return str(self.homework_request)

class ForumTopic(Forum):
    course = models.ForeignKey('Course')    
    # TODO

    def __unicode__(self):
        return str(self.course)

class ForumPost(models.Model):
    name = models.CharField(max_length=250)
    forum = models.ForeignKey('Forum')
    text = models.CharField(max_length=5000, blank=True, null=True)
    datetime = models.DateTimeField(auto_now=True)

    posted_by = models.ForeignKey('jUser', related_name='question_posted')
    anonymous = models.BooleanField(default=False)

    upvoted_by = models.ManyToManyField('jUser', related_name='question_upvoted')
    downvoted_by = models.ManyToManyField('jUser', related_name='question_downvoted')

    def __unicode__(self):
        return self.name

class ForumAnswer(models.Model):
    post = models.ForeignKey('ForumPost')
    text = models.CharField(max_length=5000)
    datetime = models.DateTimeField(auto_now=True)

    parent_answer = models.ForeignKey('ForumAnswer', null=True, blank=True)

    posted_by = models.ForeignKey('jUser', related_name='answer_posted')
    anonymous = models.BooleanField(default=False)

    upvoted_by = models.ManyToManyField('jUser', related_name='answer_upvoted')
    downvoted_by = models.ManyToManyField('jUser', related_name='answer_downvoted')

    def __unicode__(self):
        return self.text
