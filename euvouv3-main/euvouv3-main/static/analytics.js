(function(){
  function getVisitorId(){
    const match=document.cookie.match(/(?:^|; )visitor_id=([^;]+)/);
    if(match) return match[1];
    const id=Math.random().toString(36).slice(2)+Date.now().toString(36);
    document.cookie='visitor_id='+id+'; path=/; max-age=31536000';
    return id;
  }
  const visitorId=getVisitorId();
  const start=Date.now();
  fetch('/api/analytics',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'pageview',path:window.location.pathname,referrer:document.referrer,visitor_id:visitorId})});
  window.addEventListener('beforeunload',function(){
    const t=(Date.now()-start)/1000;
    navigator.sendBeacon('/api/analytics',JSON.stringify({type:'pageexit',path:window.location.pathname,visitor_id:visitorId,time_on_page:t}));
  });
  document.addEventListener('click',function(e){
    const ad=e.target.closest('.ad-click');
    if(ad){
      fetch('/api/analytics',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'ad_click',path:window.location.pathname,visitor_id:visitorId,ad_id:ad.dataset.adId||null})});
    }
  });

  if('IntersectionObserver' in window){
    const seen=new Set();
    const observer=new IntersectionObserver(function(entries){
      entries.forEach(function(entry){
        if(entry.isIntersecting){
          const el=entry.target;
          if(seen.has(el)) return;
          seen.add(el);
          fetch('/api/analytics',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'ad_impression',path:window.location.pathname,visitor_id:visitorId,ad_id:el.dataset.adId||null})});
        }
      });
    },{threshold:0.5});
    document.querySelectorAll('.ad-impression').forEach(function(el){
      observer.observe(el);
    });
  } else {
    document.querySelectorAll('.ad-impression').forEach(function(el){
      fetch('/api/analytics',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'ad_impression',path:window.location.pathname,visitor_id:visitorId,ad_id:el.dataset.adId||null})});
    });
  }
})();
