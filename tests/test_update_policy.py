from hashlib import sha256
import pytest
from agent.application.update_policy import UpdateCandidate,UpdatePolicy
def test_trusted_hash_verified_candidate_can_commit_after_health(tmp_path):
 p=tmp_path/'package'; p.write_bytes(b'package'); c=UpdateCandidate('1',sha256(b'package').hexdigest(),'release')
 policy=UpdatePolicy({'release'}); assert policy.commit_after_health(policy.stage(c,p),True)==c
def test_untrusted_corrupt_or_unhealthy_candidate_is_rejected(tmp_path):
 p=tmp_path/'package'; p.write_bytes(b'package'); c=UpdateCandidate('1','0'*64,'unknown'); policy=UpdatePolicy({'release'})
 with pytest.raises(ValueError): policy.stage(c,p)
 good=UpdateCandidate('1',sha256(b'package').hexdigest(),'release')
 with pytest.raises(RuntimeError): policy.commit_after_health(policy.stage(good,p),False)
