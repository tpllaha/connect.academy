import random
from django.db import IntegrityError
from app.models import *
from django.contrib.contenttypes.models import ContentType
from versioning.models import Revision
import inspect
import sys


class Populator:

    """ Class to populate the test database """

    def __init__(self):
        word_file = "bin/words"
        self.words = open(word_file).read().splitlines()

    def random_word(self):
        while True:
            try:
                word = random.choice(self.words).decode("utf-8", "ignore").replace("'", "")
                if len(word) > 2:
                    return word
            except UnicodeError:
                continue

    def add_admin(self, category):
        university = category.university
        user = self.add_juser(user_type=USER_TYPE_ADMIN, university=university)
        user.categories_managed.add(category)


    def add_university(self):
        while True:
            first_name = self.random_word().capitalize()
            name = first_name + " University"
            if len(University.objects.filter(name=name)) > 0:
                continue
            abbreviation = "uni" + first_name[0:3]
            if len(Category.objects.filter(abbreviation=abbreviation)) > 0:
                continue
            break

        univ = University.objects.create(name=name)

        domain = name.lower().replace(" ", ".") + ".edu"
        Domain.objects.create(name=domain, university=univ)

        connect = Category.objects.get(name="Connect.Academy")
        category = Category.objects.create(parent=connect, level=1, name=name, university=univ, abbreviation=abbreviation)
        self.add_admin(category) # make sure that every university category has an admin


    def populate_universities(self, count):
        for i in range(count):
            self.add_university()

    def create_username_juser(self, user_type):
        utype = dict(USER_TYPES)[user_type]
        nr_utypes = len(jUser.objects.filter(user_type=user_type))

        username = utype + str(nr_utypes)
        while len(jUser.objects.filter(username=username)) > 0:
            nr_utypes += 1
            username = utype + str(nr_utypes)
        return username

    def add_juser(self, user_type=None, university=None):
        if user_type == None:
            user_type = random.choice(list(USER_TYPES))[0]
        fname = self.random_word().capitalize()
        lname = self.random_word().capitalize()
        username = self.create_username_juser(user_type)
        if university is None:
            univs = University.objects.all()
            university = univs[random.randrange(len(univs))]
        active = True
        password = "1234"
        domain = university.domains.all()[0]
        major = Major.objects.all()[random.randint(0,Major.objects.all().count()-1)]
        email = username + "@" + domain.name
        user = jUser.objects.create_user(username=username, password=password,
                                         email=email, first_name=fname, last_name=lname,
                                         user_type=user_type, university=university)
        if user_type == 1:
            user.is_confirmed = True
        
        user.majors.add(major)
        user.save()
        return user # needed by add_admin()

    def populate_jusers(self, count):
        for i in range(count):
            self.add_juser()

    def populate_students(self, count):
        for i in range(count):
            self.add_juser(USER_TYPE_STUDENT)

    def populate_majors(self, count):  
        for i in range(count):
            major = self.random_word().capitalize() + " " + self.random_word().capitalize()
            major_list = major.split()
            abbreviation = major_list[0][0:2] + " " + major_list[1][0:2]
            m = Major.objects.create(name=major, abbreviation=abbreviation)
            m.save()
        
    def populate_admins(self, count):
        for i in range(count):
            self.add_juser(USER_TYPE_ADMIN)

    def populate_professors(self, count):
        for i in range(count):
            self.add_juser(USER_TYPE_PROFESSOR)

    def add_category(self):
        categories = Category.objects.filter(level__gte=1)
        if not len(categories):
            raise IntegrityError("Please load the initial data fixture!")
        parent = random.choice(categories)
        level = parent.level + 1
        fname = self.random_word().capitalize()
        lname = self.random_word().capitalize()
        name = fname + " " + lname
        abbreviation = fname[0:min(len(fname), 4)] + lname[0:min(len(lname), 4)]
        univ = parent.university
        deadline = self.add_registration_deadline()
        category = Category(parent=parent, name=name, university=univ, level=level, \
                            abbreviation=abbreviation, registration_deadline=deadline)
        category.save()

    def populate_categories(self, count):
        for i in range(count):
            self.add_category()

    def add_course_topic(self, course):
        name = ""
        description = ""
        for i in range(random.randint(1, 4)):
            name += self.random_word() + " "
        for i in range(random.randint(10, 30)):
            description += self.random_word() + " "
        CourseTopic.objects.create(name=name, description=description, course=course)

    def populate_course_topics(self, course, count=10):
        for i in range(count):
            self.add_course_topic(course)

    def add_course(self, leaf_categories=None):
        if not leaf_categories:
            leaf_categories = [c for c in Category.objects.all() if self.is_leaf(c)]
        
        course_id = random.randint(100000, 999999)
        name = self.random_word() + " " + self.random_word() + " " + self.random_word()
        course_type = random.choice(list(COURSE_TYPES))[0]
        credits = random.randint(1, 10)
        description = ""
        for i in range(0, random.randint(10, 20)):
            description = description + self.random_word() + " "
        category = random.choice(leaf_categories)

        university = category.university
        if not university:
            print "Category %s has no university." % category.name
        # Add additional description
        # Add all other fields
        course = Course.objects.create(course_id=course_id, course_type=course_type, name=name,
                        credits=credits, description=description, category=category,
                        university=university)

        self.populate_course_topics(course, count=random.randint(5,10))

        professors = list(jUser.objects.filter(user_type=USER_TYPE_PROFESSOR, university=university))
        


        if not professors:
            self.add_juser(user_type=USER_TYPE_PROFESSOR, university=university)
            professors = list(jUser.objects.filter(user_type=USER_TYPE_PROFESSOR, university=university))
        random.shuffle(professors)
        nr_professors = random.randint(1, min(3,len(professors)))
        for i in range(nr_professors):
            pcr = ProfessorCourseRegistration(professor=professors[i], course=course, is_approved=True)
            pcr.save()

    def populate_courses(self, count):
        categories = Category.objects.all()
        leaf_categories = [c for c in categories if self.is_leaf(c)]
        for i in range(count):
            self.add_course(leaf_categories)

    def is_leaf(self,category):
        return category.parent and category.children.count() == 0

    def populate_registrations(self):
        courses = Course.objects.all()
        for course in courses:
            university = course.university
            students = list(jUser.objects.filter(user_type=USER_TYPE_STUDENT, university=university))
            nr_students = len(students)
            nr_registered = int(1.0 * nr_students * random.randint(5,20) / 100.0)
            random.shuffle(students)
            for i in range(nr_registered):
                is_approved = random.random() > 0.1
                StudentCourseRegistration.objects.create(student=students[i], course=course, is_approved=is_approved)


    def add_registration_deadline(self):
        start = datetime.now() + timedelta(days=random.randint(-10,-1),hours=random.randint(7,22),minutes=random.randint(0,59))
        deadline = datetime.now()
        ddl = CourseRegistrationDeadline.objects.create(start=start, end=deadline)
        ddl.save()
        return ddl

    def populate_course_documents(self):
        courses = Course.objects.all()
        for course in courses:
            topics = course.course_topics.all()
            students = course.students.all()
            for topic in topics: 
                if random.randint(1,10) > 5 and len(students) > 0:
                    s = students[random.randint(0,len(students)-1)]
                    CourseDocument.objects.create(name=self.random_word().capitalize(), \
                                                  description = 5 * self.random_word().capitalize(), \
                                                  course_topic  = topic,\
                                                  course = course,\
                                                  submitter = s,\
                                                  submit_time = datetime.now()).save()


    def populate_course_homework_request(self):
        courses = Course.objects.all()
        for course in courses:
            topics = course.course_topics.all()
            students = course.students.all()
            d = Deadline.objects.create(end=datetime.now())
            d.save()
            for topic in topics: 
                if random.randint(1,10) > 5 and len(students) > 0:
                    s = students[random.randint(0,len(students)-1)]
                    CourseHomeworkRequest.objects.create(name=self.random_word().capitalize(), \
                                                         description = 5 * self.random_word().capitalize(), \
                                                         course_topic  = topic,\
                                                         course = course,\
                                                         submitter = s,\
                                                         deadline = d).save()


    def populate_course_homework_submission(self):
        courses = Course.objects.all()
        for course in courses:
            homework_requests = CourseHomeworkRequest.objects.filter(course=course)
            students = course.students.all()
            submit_time = datetime.now()
            for homework_request in homework_requests: 
                if random.randint(1,10) > 5 and len(students) > 0:
                    s = students[random.randint(0,len(students)-1)]
                    CourseHomeworkSubmission.objects.create(name=self.random_word().capitalize(), \
                                                         homework_request = homework_request,\
                                                         course = course,\
                                                         submit_time = submit_time,\
                                                         submitter = s).save()



    def populate_course_homework_grade(self):
        homework_requests = CourseHomeworkRequest.objects.all()
        students = jUser.objects.filter(user_type=0)
        for homework_request in homework_requests: 
            if random.randint(1,10) > 5 and len(students) > 0:
                s = students[random.randint(0,len(students)-1)]
                CourseHomeworkGrade.objects.create(homework_request = homework_request,\
                                                   student =s,\
                                                   submitter = s).save()


    def add_comment(self, course):
        comment = ""
        for i in range(random.randint(10, 100)):
            comment = comment + self.random_word() + " "
        poster = random.choice(jUser.objects.all())
        anonymous = random.random() < 0.2
        commObj = Review(review=comment, course=course, posted_by=poster)
        commObj.save()

    def populate_comments(self, count):
        courses = Course.objects.all()
        for i in range(count):
            course = random.choice(courses)
            self.add_comment(course)

    def add_rating(self, course):
        rating = ""
        users = list(jUser.objects.all())
        random.shuffle(users)
        rating_types = [] + list(RATING_TYPES)
        random.shuffle(rating_types)
        rater = None
        rat_type = None
        for rating_type in rating_types:
            for user in users:
                if len(Rating.objects.filter(user=user, course=course, rating_type=rating_type[0])) == 0:
                    rat_type = rating_type[0]
                    rater = user
                    break
            if rater:
                break
        if not rater:
            return False

        rating = random.randint(1, 5)
        if rat_type != PROFESSOR_R:
            rat = Rating(user=rater, course=course, rating=rating, rating_type=rat_type)
            rat.save()
        else:
            profs = course.professors.all()
            if len(profs) == 0:
                # If the course for some reason has no professors yet, add one. 
                prof = random.choice(jUser.objects.filter(user_type=USER_TYPE_PROFESSOR) )
                ProfessorCourseRegistration.objects.create(course=course, professor=prof, is_approved=True)
            prof = random.choice(course.professors.all())
            rat = Rating(user=rater, course=course, rating=rating, rating_type=rat_type, professor=prof)
            rat.save()
        return True

    def populate_ratings(self, count):
        courses = Course.objects.all()
        i = 0
        while i < count:
            course = random.choice(courses)
            if len(Rating.objects.filter(course=course)) >= len(jUser.objects.all()) * len(RATING_TYPES):
                continue
            while not self.add_rating(course):
                pass
            i += 1


    def populate_forum_post(self, forum):
        students = jUser.objects.all()
        if forum.forum_type == FORUM_COURSE:
            course = forum.forumcourse.course
            students = course.students.all()
            if not students:
                return ;
        posted_by = random.choice(students)
        name = self.random_word() + " " + self.random_word()
        text = ""
        for i in range(random.randint(0,10)):
            text = text + self.random_word() + " "
        anon = False
        if random.random() < 0.1:
            anon = True
        tags = forum.get_tags()
        tag = random.choice(tags)
        ForumPost.objects.create(name=name, forum=forum, text=text, posted_by=posted_by, anonymous=anon, tag=tag)

    def populate_forum_posts(self, count):
        forums = Forum.objects.all()
        for i in range(count):
            forum = random.choice(forums)
            self.populate_forum_post(forum)

    def populate_forum_answer(self, forum_post):
        forum = forum_post.forum
        students = jUser.objects.all()
        if forum.forum_type == FORUM_COURSE:
            course = forum.forumcourse.course
            students = course.students.all()
            if not students:
                return ;
        posted_by = random.choice(students)
        text = ""
        for i in range(random.randint(10,50)):
            text = text + self.random_word() + " "
        anon = False
        if random.random() < 0.1:
            anon = True
        parent_answer = None
        if random.random() < 0.4:
        # if random.random() < 1:
            answers = list(ForumAnswer.objects.filter(post=forum_post, parent_answer=None))
            if random.random() < 0.5:
                # post to a leaf
                while len(answers):
                    parent_answer = random.choice(answers)
                    answers = list(ForumAnswer.objects.filter(post=forum_post, parent_answer=parent_answer))
            else:
                # post a reply
                if len(answers):
                    parent_answer = random.choice(answers)

        ForumAnswer.objects.create(post=forum_post, text=text, posted_by=posted_by, anonymous=anon, parent_answer=parent_answer)

    def populate_forum_answers(self, count):
        forum_posts = ForumPost.objects.all()
        for i in range(count):
            forum_post = random.choice(forum_posts)
            self.populate_forum_answer(forum_post)

    def populate_forum_upvotes_object(self, obj, students):
        random.shuffle(students)
        nr_students = len(students)
        for i in range( random.randint(0, nr_students-1) ):
            obj.upvoted_by.add(students[i])

    def populate_forum_upvotes(self):
        forums = Forum.objects.all()
        for forum in forums:
            students = list(jUser.objects.all())
            if forum.forum_type == FORUM_COURSE:
                course = forum.forumcourse.course
                students = list(course.students.all())
                if not students:
                    return
            posts = forum.forumpost_set.all()
            for post in posts:
                self.populate_forum_upvotes_object(post, students)
                answers = post.forumanswer_set.all()
                for answer in answers:
                    self.populate_forum_upvotes_object(answer, students)

    def check_dependencies(self, nr_universities=0, nr_students=0, nr_categories=0,
                           nr_professors=0, nr_courses=0, nr_reviews=0, nr_ratings=0,
                           nr_forum_posts=0, nr_forum_answers=0):
        if len(University.objects.all()) == 0:
            raise IntegrityError("Please load the initial data fixture!")
        if len(Category.objects.all()) < 2:
            raise IntegrityError("Please load the initial data fixture!")
        if len(jUser.objects.all()) < 2:
            raise IntegrityError("Please load the initial data fixture!")
        if nr_courses + len(Course.objects.all()) > 0 \
            and (nr_professors + len(jUser.objects.filter(user_type=USER_TYPE_PROFESSOR)) <= 0):
            raise RuntimeError("Not enough professors in the DB")
        if nr_reviews + len(Review.objects.all()) > 0 \
            and (nr_courses + len(Course.objects.all()) <= 0):
            raise RuntimeError("Not enough courses in the DB")
        if nr_ratings + len(Rating.objects.all()) > (nr_courses + len(Course.objects.all())) * \
            (nr_students + len(jUser.objects.all())) * len(RATING_TYPES):
            raise RuntimeError("Not enough courses and/or users in the DB")
        if nr_forum_posts > 0 and nr_courses + len(Course.objects.all()) < 10:
            raise RuntimeError("Not enough courses in the DB for the forum posts")
        if nr_forum_answers > 0 and nr_forum_posts + len(ForumPost.objects.all()) <= 0:
            raise RuntimeError("Not enough forum posts in the DB for the forum answers")

    def populate_database(self, nr_universities=0, nr_students=0, nr_majors=0, nr_categories=0,
                          nr_professors=0, nr_courses=0, nr_reviews=0, nr_ratings=0,
                          nr_forum_posts=0, nr_forum_answers=0, nr_homework_requests=0, nr_homework_submissions=0,
                          nr_homework_grades=0, nr_wikis=0, nr_wiki_contributions=0):

        print "check_dependencies... "
        self.check_dependencies(nr_universities=nr_universities, nr_students=nr_students, nr_categories=nr_categories,
                                nr_professors=nr_professors, nr_courses=nr_courses, nr_reviews=nr_reviews,
                                nr_ratings=nr_ratings, nr_forum_posts=nr_forum_posts, nr_forum_answers=nr_forum_answers)
        print "ok"

        if nr_majors: print "populate majors...."
        self.populate_majors(nr_majors)
        if nr_majors: print "ok"

        if nr_universities: print "populate_universities... "
        self.populate_universities(nr_universities)
        if nr_universities: print "ok"

        if nr_students: print "populate_students... "
        self.populate_students(nr_students)
        print "ok"

        if nr_professors: print "populate_professors... "
        self.populate_professors(nr_professors)
        if nr_professors: print "ok"

        if nr_categories: print "populate_categories... "
        self.populate_categories(nr_categories)
        if nr_categories: print "ok"

        if nr_courses: print "populate_courses... "
        self.populate_courses(nr_courses)
        if nr_courses: print "ok"

        if nr_homework_requests: print "populate homework_request..."
        self.populate_course_homework_request()
        if nr_homework_requests: print "ok"

        if nr_homework_submissions: print "populate homework_submissions..."
        self.populate_course_homework_submission()
        if nr_homework_submissions: print "ok"

        if nr_homework_grades: print "populate homework_grades...."
        self.populate_course_homework_grade()
        if nr_homework_grades: print "ok"

        if nr_wikis > 0: 
            print "populate wikis...."
            self.populate_wiki_page()
        if nr_wikis: print "ok"

        if nr_wiki_contributions: print "populate wiki contributions...."
        self.populate_wiki_contributions()
        if nr_wiki_contributions: print "ok"

        if nr_reviews: print "populate_comments... "
        self.populate_comments(nr_reviews)
        if nr_reviews: print "ok"

        if nr_ratings: print "populate_ratings... "
        self.populate_ratings(nr_ratings)
        if nr_ratings: print "ok"

        if nr_forum_posts: print "populate_forum_posts... "
        self.populate_forum_posts(nr_forum_posts)
        if nr_forum_posts: print "ok"

        if nr_forum_answers: print "populate_forum_answers... "
        self.populate_forum_answers(nr_forum_answers)
        if nr_forum_answers: print "ok"

    # Populate the database with small sizes
    @staticmethod
    def populate_small():
        populator = Populator()
        populator.populate_database(nr_universities=2, nr_students=200, nr_majors= 30, nr_categories=20,
            nr_professors=20, nr_courses=15, nr_reviews=20, nr_ratings=100,  nr_homework_requests=1,
            nr_homework_submissions=1, nr_homework_grades=1, nr_wikis=1, nr_wiki_contributions=1 )

        print "populate_registrations... "
        populator.populate_registrations()
        print "ok"

        populator.populate_database(nr_forum_posts=50, nr_forum_answers=300)

        print "populate_forum_upvotes... "
        populator.populate_forum_upvotes()
        print "ok"

        print "populate_appointments..."
        Populator.populate_appointments()
        print "ok"


    @staticmethod
    def populate_xsmall():
        populator = Populator()
        populator.populate_database(nr_universities=1, nr_students=40, nr_majors= 30, nr_categories=15,
            nr_professors=10, nr_courses=10, nr_reviews=20, nr_ratings=30, nr_homework_requests=1,
            nr_homework_submissions=1, nr_homework_grades=1, nr_wikis=1, nr_wiki_contributions=1)

        print "populate_registrations... "
        populator.populate_registrations()
        print "ok"

        populator.populate_database(nr_forum_posts=20, nr_forum_answers=80)

        print "populate_forum_upvotes... "
        populator.populate_forum_upvotes()
        print "ok"

        print "populate_appointments..."
        Populator.populate_appointments()
        print "ok"


    def populate_course_intense():
        populator = Populator()
        populator.populate_database(nr_universities=10, nr_students=50, nr_categories=200,
            nr_professors=50, nr_courses=700, nr_reviews=0, nr_ratings=1000)

        print "populate_registrations... "
        populator.populate_registrations()
        print "ok"


    @staticmethod
    def populate_course_appointments():
        courses = Course.objects.all()
        if len(courses) == 0:
            print "No courses in the DB. Populate them first."
            return False

        current_date = datetime.now()
        
        index = 0
        for course in courses:
            course_topics = course.course_topics.all()
            for i in range(len(course_topics)):
                topic = course_topics[i]
                start = current_date + timedelta(days=random.randint(0,6),hours=random.randint(7,22),minutes=random.randint(0,59))
                end = start + timedelta(hours=random.randint(1,3))
                l = "Location " + str(index)
                d = "CourseAppointment " + str(index)
                appointment = CourseAppointment(start=pytz.utc.localize(start),end=pytz.utc.localize(end),location=l,description=d,course=course,course_topic=topic)
                appointment.save()
                index += 1

        return True


    @staticmethod
    def populate_personal_appointments():
        users = jUser.objects.all()
        if len(users) == 0:
            print "No users in the DB. Populate them first"
            return False

        current_date = datetime.now()
        
        index = 0
        for user in users:
            for i in range(random.randint(1,5)):
                start = current_date + timedelta(days=random.randint(0,6),hours=random.randint(7,22),minutes=random.randint(0,59))
                end = start + timedelta(hours=random.randint(1,3))
                l = "Location " + str(index)
                d = "PersonalAppointment " + str(index)
                appointment = PersonalAppointment(start=pytz.utc.localize(start),end=pytz.utc.localize(end),location=l,description=d,user=user)
                appointment.save()
                index += 1
        return True

    @staticmethod
    def populate_appointments():
        print "\tPopulating course appointments ..."
        status_course = Populator.populate_course_appointments()
        print "\tPopulating personal appointments ..."
        status_person = Populator.populate_personal_appointments()

        if status_course and status_person:
            print "\tSuccessfully populated the appointment tables"


    def populate_wiki_page(self):
        courses = Course.objects.all()
        for course in courses: 
            if random.randint(1,10) > 5:
                wiki = ""
                for i in range(50):
                    wiki = wiki + " " + self.random_word().capitalize()
                WikiPage.objects.create(course=course, content=wiki)
                


    def populate_wiki_contributions(self):
        users = jUser.objects.all()
        wikis = WikiPage.objects.all()
        for wiki in wikis:
            user = users[random.randint(0, len(users)-1)]
            wiki.content += " REVISED"
            wiki_ctype = ContentType.objects.get(app_label="app", model="wikipage")
            content_object = wiki_ctype.get_object_for_this_type(pk=wiki.id)
            revision = Revision.objects.filter(content_type=wiki_ctype, object_id=content_object.pk).latest('created_at')
            WikiContributions.objects.create(wiki=wiki, user=user, revision=revision).save()



