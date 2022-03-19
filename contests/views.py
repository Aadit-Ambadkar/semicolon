import datetime
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Contest, ContestProblem, Registration
from .forms import RegisterForm, ProblemForm
from problemset.models import Submission

# Create your views here.

def home(request):
    contests = Contest.objects.all()
    for contest in contests:
        contest.joined = False

        user_registration = Registration.objects.filter(
            user_id=request.user.id,
            contest_id=contest.id
        )
        if(len(user_registration) > 0):
            contest.joined = True
            time_diff = datetime.timedelta(minutes=contest.time_limit)
            contest.user_end_time = user_registration[0].time_joined + time_diff
            if contest.user_end_time > contest.end_time:
                contest_user_end_time = contest.end_time
            if timezone.now() <= contest.user_end_time:
                contest.running = True

        if timezone.now() > contest.end_time:
            contest.ended = True
        elif timezone.now() >= contest.start_time:
            contest.started = True
            messages.info(request, f"{contest.name} is in progress!")

    context = {
        'contests': reversed(contests)
    }
    return render(request, 'contests/home.html', context)

def confirm(request, index):
    contest = Contest.objects.get(pk=index)

    if timezone.now() > contest.end_time:
        messages.error(request, f"You cannot take {contest.name} officially anymore.")
        return redirect('contests-home')

    if not request.user.is_authenticated:
        messages.error(request, "Please log in before joining the contest!")
        return redirect(f'/login/?next={request.path}')
    
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            agreed = form.cleaned_data.get('agree')

            if(agreed):
                new_user_registration = Registration(
                    user_id=request.user.id,
                    contest_id = contest.id
                )
                new_user_registration.save()
                messages.success(request, f"You have joined {contest.name}!")
                return redirect(f'/contests/{index}/arena/')

    else:
        form = RegisterForm()

    user_registration = Registration.objects.filter(
        user_id=request.user.id,
        contest_id=index
    )
    if(len(user_registration) > 0):
        messages.success(request, f"You already have joined this contest!")
        return redirect(f'/contests/{index}/arena/')

    context = {
        'contest': contest,
        'form': form,
    }
    return render(request, 'contests/confirm.html', context)

def arena(request, index):
    contest = Contest.objects.get(pk=index)
    user_registration = Registration.objects.filter(
        user_id=request.user.id,
        contest_id=index
    )
    contest_problems = ContestProblem.objects.filter(
        contest=contest
    )

    if request.method == 'POST':
        form = ProblemForm(request.POST)
        redirect_url = '/contests/' + str(index) + '/arena/'
        if form.is_valid():
            problem_id = int(form.cleaned_data.get('problem_id'))
            problem = contest_problems[problem_id].problem
            user_answer = form.cleaned_data.get('answer')
            redirect_url += '#' + str(problem_id + 1)

            user_submissions = Submission.objects.filter(
                user_id=request.user.id,
                problem_id=problem.id
            )
            problem_solved = (user_answer == problem.correct_answer)

            if(problem_solved):
                messages.success(request, f"You answer {user_answer} for problem {problem_id + 1} is correct!")
            else:
                messages.error(request, f"You answer {user_answer} is problem {problem_id + 1} is wrong!")

            if(len(user_submissions) == 0):
                new_user_submission = Submission(
                    user_id=request.user.id,
                    problem_id=problem.id,
                    problem_solved=problem_solved,
                    penalty=0
                )
                new_user_submission.save()
            else:
                current_user_submission = user_submissions[0]
                current_user_submission.problem_solved |= problem_solved
                current_user_submission.save()

        return redirect(redirect_url)
    else:
        idx = 0
        for problem in contest_problems:
            problem.form = ProblemForm(initial={'problem_id': idx})
            idx += 1
    
    if timezone.now() < contest.start_time:
        messages.error(request, f"{contest.name} hasn't started yet!")
        return redirect('contests-home')
    elif timezone.now() <= contest.end_time:
        if not request.user.is_authenticated:
            messages.error(request, f"Please login before taking {contest.name}! Note you must have started this contest on your account!")
            return redirect(f'/login/?next={request.path}')
        elif len(user_registration) == 0:
            messages.error(request, f"You can't take {contest.name} because you haven't joined! Please confirm before joining!")
            return redirect(f'/contests/{index}/confirm')
        else:
            time_diff = datetime.timedelta(minutes=contest.time_limit)
            contest.user_end_time = user_registration[0].time_joined + time_diff
            if contest.user_end_time > contest.end_time:
                contest.user_end_time = contest.end_time
            
            if timezone.now() <= contest.user_end_time:
                contest.running = True
            else:
                messages.info(request, "Your attempt for the contest has finished. You can view and submit the problems unofficially. \
                Make sure to follow the rules regarding discussion!")
    else:
        messages.info(request, "The contest is over, but you can view and submit the problems unofficially.")


    for problem in contest_problems:
        user_submissions = Submission.objects.filter(
            user_id=request.user.id,
            problem_id=problem.problem.id
        )
        problem.solved = len(user_submissions) > 0 and user_submissions[0].problem_solved

    context = {
        'contest': contest,
        'contest_problems': contest_problems
    }
    return render(request, 'contests/arena.html', context)
