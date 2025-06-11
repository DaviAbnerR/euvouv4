(function(){
  function hasConsent(){
    return document.cookie.split('; ').includes('cookie_consent=true');
  }
  function setConsent(){
    document.cookie='cookie_consent=true; path=/; max-age=31536000';
  }
  function loadAnalytics(){
    if(window.analyticsLoaded) return;
    var s=document.createElement('script');
    s.src='/static/analytics.js';
    document.body.appendChild(s);
    if(window.gaMeasurementId){
      var ga=document.createElement('script');
      ga.async=true;
      ga.src='https://www.googletagmanager.com/gtag/js?id='+window.gaMeasurementId;
      document.head.appendChild(ga);
      var inline=document.createElement('script');
      inline.text="window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','"+window.gaMeasurementId+"');";
      document.head.appendChild(inline);
    }
    window.analyticsLoaded=true;
  }
  function showBanner(){
    var banner=document.createElement('div');
    banner.className='cookie-banner bg-dark text-white text-center';
    banner.style.position='fixed';
    banner.style.bottom='0';
    banner.style.left='0';
    banner.style.right='0';
    banner.style.zIndex='1200';
    banner.style.padding='10px';
    banner.innerHTML='Este site usa cookies para melhorar sua experiência. <button class="btn btn-primary btn-sm ms-2">Aceitar</button>';
    banner.querySelector('button').addEventListener('click',function(){
      setConsent();
      banner.remove();
      loadAnalytics();
    });
    document.body.appendChild(banner);
  }
  if(hasConsent()){
    loadAnalytics();
  }else{
    if(document.readyState==='loading'){
      document.addEventListener('DOMContentLoaded',showBanner);
    }else{
      showBanner();
    }
  }
})();
