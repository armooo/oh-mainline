# This file is part of OpenHatch.
# Copyright (C) 2010 Jack Grigg
# Copyright (C) 2010 John Stumpo
# Copyright (C) 2011 Krzysztof Tarnowski (krzysztof.tarnowski@ymail.com)
# Copyright (C) 2010, 2011 OpenHatch, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from mysite.missions.base.views import *
from mysite.missions.svn import forms, controllers
import mysite.missions.base.views

### POST handlers
###
### Forms submit to this, and we use these to validate input and/or
### modify the information stored about the user, such as recording
### that a mission was successfully completed.
@login_required
def resetrepo(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    controllers.SvnRepository(request.user.username).reset()
    controllers.unset_mission_completed(request.user.get_profile(), 'svn_checkout')
    controllers.unset_mission_completed(request.user.get_profile(), 'svn_diff')
    controllers.unset_mission_completed(request.user.get_profile(), 'svn_commit')
    if 'stay_on_this_page' in request.GET:
        return HttpResponseRedirect(reverse('svn_main_page'))
    else:
        return HttpResponseRedirect(reverse('svn_checkout'))

@login_required
def diff_submit(request):
    # Initialize data array and some default values.
    data = {}
    data['svn_diff_form'] = forms.DiffForm()
    data['svn_diff_error_message'] = ''
    if request.method == 'POST':
        form = forms.DiffForm(request.POST)
        if form.is_valid():
            try:
                controllers.SvnDiffMission.validate_diff_and_commit_if_ok(request.user.username, form.cleaned_data['diff'])
                controllers.set_mission_completed(request.user.get_profile(), 'svn_diff')
                return HttpResponseRedirect(reverse('svn_diff'))
            except controllers.IncorrectPatch, e:
                data['svn_diff_error_message'] = str(e)
        data['svn_diff_form'] = form
    request.method = 'GET'
    return Diff.as_view()(request, extra_context_data=data)

@login_required
def checkout_submit(request):
    # Initialize data array and some default values.
    data = {}
    data['svn_checkout_form'] = forms.CheckoutForm()
    data['svn_checkout_error_message'] = ''
    if request.method == 'POST':
        form = forms.CheckoutForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['secret_word'] == controllers.SvnCheckoutMission.get_secret_word(request.user.username):
                controllers.set_mission_completed(request.user.get_profile(), 'svn_checkout')
                return HttpResponseRedirect(reverse('svn_checkout'))
            else:
                data['svn_checkout_error_message'] = 'The secret word is incorrect.'
        data['svn_checkout_form'] = form
    # If we get here, just hack up the request object to pretend it is a GET
    # so the dispatch system in the class-based view can use the GET handler.
    request.method = 'GET'
    return Checkout.as_view()(request, extra_context_data=data)

### All GET handlers are subclasses of this so that tedious template
### context variable generation is handled elsewhere.
class SvnBaseView(mysite.missions.base.views.MissionBaseView):
    mission_name = 'Using Subversion'
    def get_context_data(self, *args, **kwargs):
        ### For now, we use the MissionPageState object to track a few things.
        ### Eventually, the missions base will stop using the PageState object,
        ### and all the work that class does will get merged into MissionBaseView.
        data = super(SvnBaseView, self).get_context_data(*args, **kwargs)
        state = MissionPageState(self.request, passed_data=None, mission_name=self.mission_name)
        new_data, person = state.get_base_data_dict_and_person()
        if person:
            repo = controllers.SvnRepository(self.request.user.username)
            new_data.update({
                'repository_exists': repo.exists(),
                'svn_checkout_done': controllers.mission_completed(person, 'svn_checkout'),
                'svn_diff_done': controllers.mission_completed(person, 'svn_diff'),
                'svn_commit_done': controllers.mission_completed(person, 'svn_commit'),
            })
            if new_data['repository_exists']:
                new_data.update({
                        'checkout_url': repo.public_trunk_url(),
                        'secret_word_file': controllers.SvnCheckoutMission.SECRET_WORD_FILE,
                        'file_for_svn_diff': controllers.SvnDiffMission.FILE_TO_BE_PATCHED,
                        'new_secret_word': controllers.SvnCommitMission.NEW_SECRET_WORD,
                        'commit_username': self.request.user.username,
                        'commit_password': repo.get_password()})
        data.update(new_data)
        return data

### Normal GET handlers. These are usually pretty short. They are based on
### SvnBaseView.
class MainPage(SvnBaseView):
    this_mission_page_short_name = 'Start page'
    template_name = 'missions/svn/main_page.html'

class LongDescription(SvnBaseView):
    this_mission_page_short_name = 'About Subversion'
    template_name =  'missions/svn/about_svn.html'

class Checkout(SvnBaseView):
    login_required = True
    this_mission_page_short_name = 'Checking out'
    template_name = 'missions/svn/checkout.html'

    def get_context_data(self, *args, **kwargs):
        data = super(Checkout, self).get_context_data(*args, **kwargs)
        data['svn_checkout_form'] = forms.CheckoutForm()
        return data

class Diff(SvnBaseView):
    login_required = True
    this_mission_page_short_name = 'Diffing your changes'
    mission_step_prerequisite = 'svn_checkout'
    template_name = 'missions/svn/diff.html'

    def get_context_data(self, *args, **kwargs):
        data = super(Diff, self).get_context_data(*args, **kwargs)
        data['svn_diff_form'] = forms.DiffForm()
        return data

class Commit(SvnBaseView):
    login_required = True
    this_mission_page_short_name = 'Committing your changes'
    mission_step_prerequisite = 'svn_diff'
    template_name = 'missions/svn/commit.html'

@login_required
def commit_poll(request):
    return HttpResponse(simplejson.dumps(controllers.mission_completed(request.user.get_profile(), 'svn_commit')))
