import os
from typing import Optional

from modelscope.hub.errors import GitError, InvalidParameter, NotLoginException
from modelscope.utils.constant import (DEFAULT_DATASET_REVISION,
                                       DEFAULT_MODEL_REVISION)
from modelscope.utils.logger import get_logger
from .api import ModelScopeConfig
from .git import GitCommandWrapper
from .utils.utils import get_endpoint

logger = get_logger()


class Repository:
    """A local representation of the model git repository.
    """

    def __init__(self,
                 model_dir: str,
                 clone_from: str,
                 revision: Optional[str] = DEFAULT_MODEL_REVISION,
                 auth_token: Optional[str] = None,
                 git_path: Optional[str] = None):
        """
        Instantiate a Repository object by cloning the remote ModelScopeHub repo
        Args:
            model_dir(`str`):
                The model root directory.
            clone_from:
                model id in ModelScope-hub from which git clone
            revision(`Optional[str]`):
                revision of the model you want to clone from. Can be any of a branch, tag or commit hash
            auth_token(`Optional[str]`):
                token obtained when calling `HubApi.login()`. Usually you can safely ignore the parameter
                as the token is already saved when you login the first time, if None, we will use saved token.
            git_path:(`Optional[str]`):
                The git command line path, if None, we use 'git'
        """
        self.model_dir = model_dir
        self.model_base_dir = os.path.dirname(model_dir)
        self.model_repo_name = os.path.basename(model_dir)
        if auth_token:
            self.auth_token = auth_token
        else:
            self.auth_token = ModelScopeConfig.get_token()

        git_wrapper = GitCommandWrapper()
        if not git_wrapper.is_lfs_installed():
            logger.error('git lfs is not installed, please install.')

        self.git_wrapper = GitCommandWrapper(git_path)
        os.makedirs(self.model_dir, exist_ok=True)
        url = self._get_model_id_url(clone_from)
        if os.listdir(self.model_dir):  # directory not empty.
            remote_url = self._get_remote_url()
            remote_url = self.git_wrapper.remove_token_from_url(remote_url)
            if remote_url and remote_url == url:  # need not clone again
                return
        self.git_wrapper.clone(self.model_base_dir, self.auth_token, url,
                               self.model_repo_name, revision)

        if git_wrapper.is_lfs_installed():
            git_wrapper.git_lfs_install(self.model_dir)  # init repo lfs

        # add user info if login
        self.git_wrapper.add_user_info(self.model_base_dir,
                                       self.model_repo_name)
        if self.auth_token:  # config remote with auth token
            self.git_wrapper.config_auth_token(self.model_dir, self.auth_token)

    def _get_model_id_url(self, model_id):
        url = f'{get_endpoint()}/{model_id}.git'
        return url

    def _get_remote_url(self):
        try:
            remote = self.git_wrapper.get_repo_remote_url(self.model_dir)
        except GitError:
            remote = None
        return remote

    def push(self,
             commit_message: str,
             branch: Optional[str] = DEFAULT_MODEL_REVISION,
             force: bool = False):
        """Push local files to remote, this method will do.
           git pull
           git add
           git commit
           git push
        Args:
            commit_message (str): commit message
            branch (Optional[str], optional): which branch to push.
            force (Optional[bool]): whether to use forced-push.
        """
        if commit_message is None or not isinstance(commit_message, str):
            msg = 'commit_message must be provided!'
            raise InvalidParameter(msg)
        if not isinstance(force, bool):
            raise InvalidParameter('force must be bool')

        if not self.auth_token:
            raise NotLoginException('Must login to push, please login first.')

        self.git_wrapper.config_auth_token(self.model_dir, self.auth_token)
        self.git_wrapper.add_user_info(self.model_base_dir,
                                       self.model_repo_name)

        url = self.git_wrapper.get_repo_remote_url(self.model_dir)
        self.git_wrapper.pull(self.model_dir)
        self.git_wrapper.add(self.model_dir, all_files=True)
        self.git_wrapper.commit(self.model_dir, commit_message)
        self.git_wrapper.push(
            repo_dir=self.model_dir,
            token=self.auth_token,
            url=url,
            local_branch=branch,
            remote_branch=branch)


class DatasetRepository:
    """A local representation of the dataset (metadata) git repository.
    """

    def __init__(self,
                 repo_work_dir: str,
                 dataset_id: str,
                 revision: Optional[str] = DEFAULT_DATASET_REVISION,
                 auth_token: Optional[str] = None,
                 git_path: Optional[str] = None):
        """
        Instantiate a Dataset Repository object by cloning the remote ModelScope dataset repo
        Args:
            repo_work_dir(`str`):
                The dataset repo root directory.
            dataset_id:
                dataset id in ModelScope from which git clone
            revision(`Optional[str]`):
                revision of the dataset you want to clone from. Can be any of a branch, tag or commit hash
            auth_token(`Optional[str]`):
                token obtained when calling `HubApi.login()`. Usually you can safely ignore the parameter
                as the token is already saved when you login the first time, if None, we will use saved token.
            git_path:(`Optional[str]`):
                The git command line path, if None, we use 'git'
        """
        self.dataset_id = dataset_id
        self.repo_work_dir = repo_work_dir
        self.repo_base_dir = os.path.dirname(repo_work_dir)
        self.repo_name = os.path.basename(repo_work_dir)
        self.revision = revision
        if auth_token:
            self.auth_token = auth_token
        else:
            self.auth_token = ModelScopeConfig.get_token()

        self.git_wrapper = GitCommandWrapper(git_path)
        os.makedirs(self.repo_work_dir, exist_ok=True)
        self.repo_url = self._get_repo_url(dataset_id=dataset_id)

    def clone(self) -> str:
        # check local repo dir, directory not empty.
        if os.listdir(self.repo_work_dir):
            remote_url = self._get_remote_url()
            remote_url = self.git_wrapper.remove_token_from_url(remote_url)
            # no need clone again
            if remote_url and remote_url == self.repo_url:
                return ''

        logger.info('Cloning repo from {} '.format(self.repo_url))
        self.git_wrapper.clone(self.repo_base_dir, self.auth_token,
                               self.repo_url, self.repo_name, self.revision)
        return self.repo_work_dir

    def push(self,
             commit_message: str,
             branch: Optional[str] = DEFAULT_DATASET_REVISION,
             force: bool = False):
        """Push local files to remote, this method will do.
           git pull
           git add
           git commit
           git push
        Args:
            commit_message (str): commit message
            branch (Optional[str], optional): which branch to push.
            force (Optional[bool]): whether to use forced-push.
        """
        if commit_message is None or not isinstance(commit_message, str):
            msg = 'commit_message must be provided!'
            raise InvalidParameter(msg)

        if not isinstance(force, bool):
            raise InvalidParameter('force must be bool')

        if not self.auth_token:
            raise NotLoginException('Must login to push, please login first.')

        self.git_wrapper.config_auth_token(self.repo_work_dir, self.auth_token)
        self.git_wrapper.add_user_info(self.repo_base_dir, self.repo_name)

        remote_url = self.git_wrapper.get_repo_remote_url(self.repo_work_dir)
        self.git_wrapper.pull(self.repo_work_dir)
        self.git_wrapper.add(self.repo_work_dir, all_files=True)
        self.git_wrapper.commit(self.repo_work_dir, commit_message)
        self.git_wrapper.push(
            repo_dir=self.repo_work_dir,
            token=self.auth_token,
            url=remote_url,
            local_branch=branch,
            remote_branch=branch)

    def _get_repo_url(self, dataset_id):
        return f'{get_endpoint()}/datasets/{dataset_id}.git'

    def _get_remote_url(self):
        try:
            remote = self.git_wrapper.get_repo_remote_url(self.repo_work_dir)
        except GitError:
            remote = None
        return remote
