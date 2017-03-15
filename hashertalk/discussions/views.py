from django.http import HttpResponse, HttpResponseRedirect
from django.views import View 
from django.views.decorators.http import require_http_methods
from django import forms
from django.shortcuts import render, get_object_or_404
from django.db.models import F, Count
from django.db.models.functions import Length
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.contenttypes.models import ContentType

from django.forms.models import model_to_dict

from .models import Post, Comment, Vote
from .models import UPVOTE, DOWNVOTE, FLAG, UNFLAG

from collections import defaultdict

def homepage(request):
    posts = Post.objects\
                .select_related("author")\
                .order_by("submission_time")[:50].values()
    
    if request.user.is_authenticated():
        posts = _append_votes_by_user(posts, request.user)

    return render(request, "home.html", context={"posts": posts})

def _append_votes_by_user(posts, user):
    # Returns a dictionary
    # key = postid
    # value = set of votes cast by this user
    # for example set('downvote', 'flag')
    post_ids = [p['id'] for p in posts]
    post_type = ContentType.objects.get_for_model(Post)
    objects = Vote.objects.\
                only('object_id', 'type_of_vote').\
                filter(content_type=post_type.id,
                    object_id__in=post_ids,
                    voter=user)

    votes_by_post = defaultdict(set)
    for obj in objects:
        vote_type_str = _vote_type_to_string(obj.type_of_vote)
        votes_by_post[obj.object_id].add(vote_type_str)

    for post in posts:
        post['votes'] = votes_by_post[post['id']]
    return posts

def _vote_type_to_string(vote_type):
    mapping = {
        UPVOTE: "upvote",
        DOWNVOTE: "downvote",
        FLAG: "flag",
        UNFLAG: "unflag"
    }
    return mapping[vote_type]

def discussion(request, post_id):
    post = Post.objects.get(pk=post_id)
    comments = Comment.objects.filter(post=post)\
                    .annotate(indent = (Length('wbs') + 1)/5 )\
                    .order_by("wbs")
    context = {"post": post, "comments": comments}
    return render(request, "discussion.html", context=context)

@login_required
@require_http_methods(['POST'])
def upvote_post(request, post_id):
    _vote_on_post(request, post_id, UPVOTE)
    return HttpResponse('OK')

@login_required
@require_http_methods(['POST'])
def downvote_post(request, post_id):
    _vote_on_post(request, post_id, DOWNVOTE)
    return HttpResponse('OK')

@login_required
@require_http_methods(['POST'])
def undo_vote_on_post(request, post_id):
    post_type = ContentType.objects.get_for_model(Post)
    Vote.objects.filter(content_type=post_type.id,
            object_id=post_id,\
            voter=request.user).delete()
    return HttpResponse('OK')
    
def _vote_on_post(request, post_id, type_of_vote):
    post = get_object_or_404(Post, pk=post_id)

    if _already_voted(request.user, post, type_of_vote):
        return

    # First, save the vote
    vote = Vote(content_object=post, voter=request.user, type_of_vote=type_of_vote)
    vote.save()

    # Next, update our denormalized columns - flags and score
    if type_of_vote == FLAG:
        post.flags = F('flags') + 1
    elif type_of_vote == UNFLAG:
        post.flags = F('flags') - 1 
    elif type_of_vote == UPVOTE:
        post.score = F('score') + 1
    elif type_of_vote == DOWNVOTE:
        post.score = F('score') - 1
    else:
        raise Exception("Invalid type of vote " + type_of_vote)
    post.save()
    
def _already_voted(user, post, type_of_vote):
    post_type = ContentType.objects.get_for_model(post)
    return Vote.objects.filter(content_type=post_type.id,
                object_id=post.id,\
                voter=user, type_of_vote=type_of_vote)\
            .exists()

@login_required
def submit(request):
    return render(request, "submit.html", context={})

@login_required
def myprofile(request):
    return render(request, "profile.html", context={})

class CreateProfileView(View):
    def post(self, request):
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return HttpResponseRedirect('/')
        else:
            return render(request, "registration/create-account.html", {"form": form})

    def get(self, request):
        form = UserCreationForm()
        return render(request, "registration/create-account.html", {"form": form})

def profile(request, userid):
    return render(request, "profile.html", context={"user": {"id": userid}})
