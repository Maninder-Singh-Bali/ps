'use strict';
(function(root){
 const label=a=>a?.status==='approved'?'Approved':a?.status==='rejected'?'Discarded':(a?.review_decision||a?.decision)==='kept'?'Kept for review':a?'Review':'Not generated';
 const history=(a,escape)=>a?.review_history?.length?`<details class="review-history"><summary>Review history · ${a.review_history.length}</summary>${a.review_history.map(h=>`<p>${escape(label(h))} · ${escape(h.note||'No note')}</p>`).join('')}</details>`:'';
 const api={label,history};if(typeof module!=='undefined')module.exports=api;else root.ReviewState=api;
})(typeof window!=='undefined'?window:this);
