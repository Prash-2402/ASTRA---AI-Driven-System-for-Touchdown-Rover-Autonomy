import * as THREE from "three";

/** GPU bake of a procedural Mars surface into equirectangular maps (colour + height).
 *  Major features are placed at their real areographic coordinates (lon E, lat N, degrees):
 *  Tharsis rise & the four great shields, Valles Marineris, Hellas & Argyre basins, the north-south
 *  dichotomy, dark albedo provinces, polar caps; crater density is higher in the southern highlands.
 *  It is a stylised, physically plausible rendering - not imagery. */
const FRAG = /* glsl */ `
precision highp float;
uniform int uMode; varying vec2 vUv;
const float PI = 3.14159265;
vec3 hash3(vec3 p){ p = vec3(dot(p,vec3(127.1,311.7,74.7)), dot(p,vec3(269.5,183.3,246.1)), dot(p,vec3(113.5,271.9,124.6))); return -1.0+2.0*fract(sin(p)*43758.5453123); }
float noise(vec3 p){ vec3 i=floor(p), f=fract(p); vec3 u=f*f*(3.0-2.0*f);
  return mix(mix(mix(dot(hash3(i),f),dot(hash3(i+vec3(1,0,0)),f-vec3(1,0,0)),u.x), mix(dot(hash3(i+vec3(0,1,0)),f-vec3(0,1,0)),dot(hash3(i+vec3(1,1,0)),f-vec3(1,1,0)),u.x),u.y),
             mix(mix(dot(hash3(i+vec3(0,0,1)),f-vec3(0,0,1)),dot(hash3(i+vec3(1,0,1)),f-vec3(1,0,1)),u.x), mix(dot(hash3(i+vec3(0,1,1)),f-vec3(0,1,1)),dot(hash3(i+vec3(1,1,1)),f-vec3(1,1,1)),u.x),u.y),u.z); }
float fbm(vec3 p){ float a=0.5, s=0.0; for(int i=0;i<7;i++){ s+=a*noise(p); p*=2.02; a*=0.5; } return s; }
vec3 dirOf(float lonDeg, float latDeg){ float lo=radians(lonDeg), la=radians(latDeg); return vec3(cos(la)*cos(lo), sin(la), -cos(la)*sin(lo)); }
float ang(vec3 a, vec3 b){ return acos(clamp(dot(a,b),-1.0,1.0)); }           // angular distance, rad
// crater field: cellular, returns height contribution
float craters(vec3 p, float scale, float density){
  vec3 q = p*scale; vec3 i=floor(q), f=fract(q); float h=0.0;
  for(int x=-1;x<=1;x++)for(int y=-1;y<=1;y++)for(int z=-1;z<=1;z++){ vec3 g=vec3(x,y,z); vec3 r=hash3(i+g);
    if (r.x*0.5+0.5 > density) continue;
    vec3 c = g + 0.5 + 0.4*r - f; float R = 0.18 + 0.22*(r.y*0.5+0.5); float d = length(c)/R;
    h += d < 1.0 ? (d*d - 1.0)*0.9 : 0.0; h += 0.35*exp(-pow((d-1.0)/0.18,2.0)); }
  return h; }
float heightAt(vec3 p, float lat, float lon){
  float h = 0.0;
  h += 0.55*smoothstep(25.0, -20.0, lat + 8.0*fbm(p*2.0));                        // dichotomy: southern highlands higher
  float th = ang(p, dirOf(-105.0, 2.0)); h += 1.1*exp(-pow(th/0.42,2.0));        // Tharsis rise
  vec4 shields[5]; shields[0]=vec4(-134.0,18.4,0.17,2.6); shields[1]=vec4(-104.4,11.9,0.07,1.6);
  shields[2]=vec4(-113.4,0.8,0.07,1.5); shields[3]=vec4(-120.5,-8.3,0.08,1.6); shields[4]=vec4(146.9,24.8,0.06,1.0);
  for(int i=0;i<5;i++){ float d = ang(p, dirOf(shields[i].x, shields[i].y))/shields[i].z;
    h += shields[i].w*exp(-d*d*2.2) - (d<0.12? shields[i].w*0.35*(1.0-d/0.12):0.0); }  // shield + summit caldera
  float vm = smoothstep(-100.0,-92.0,lon)*smoothstep(-35.0,-45.0,lon);             // Valles Marineris
  float vlat = -9.0 + 3.0*sin(radians(lon)*6.0) + 2.0*fbm(p*9.0);
  h -= 1.2*vm*exp(-pow((lat - vlat)/2.2,2.0));
  float hel = ang(p, dirOf(70.0,-42.0)); h -= 1.6*exp(-pow(hel/0.36,2.0)); h += 0.35*exp(-pow((hel-0.42)/0.08,2.0));   // Hellas + rim
  float arg = ang(p, dirOf(-43.0,-50.0)); h -= 0.9*exp(-pow(arg/0.22,2.0)); h += 0.25*exp(-pow((arg-0.27)/0.06,2.0));  // Argyre
  float south = smoothstep(30.0,-10.0,lat);
  h += 0.10*craters(p, 9.0, 0.25+0.35*south) + 0.05*craters(p, 22.0, 0.2+0.4*south) + 0.025*craters(p, 55.0, 0.35);
  h += 0.30*fbm(p*3.0) + 0.08*fbm(p*14.0);
  return h; }
void main(){
  float lon = (vUv.x - 0.5)*360.0, lat = (vUv.y - 0.5)*180.0;
  vec3 p = dirOf(lon, lat);
  float h = heightAt(p, lat, lon);
  if (uMode == 1) { gl_FragColor = vec4(vec3(clamp(h*0.22+0.45,0.0,1.0)), 1.0); return; }
  // albedo: bright dusty ochre, dark basaltic provinces, Tharsis/Arabia dust-mantled bright
  vec3 bright = vec3(0.74,0.40,0.22), mid = vec3(0.58,0.28,0.15), dark = vec3(0.24,0.14,0.10);
  float dk = 0.0;
  dk += 0.9*exp(-pow(ang(p, dirOf(69.0, 9.0))/0.20,2.0));    // Syrtis Major
  dk += 0.7*exp(-pow(ang(p, dirOf(-30.0, 46.0))/0.30,2.0));   // Acidalia Planitia
  dk += 0.7*exp(-pow(ang(p, dirOf(-40.0,-25.0))/0.28,2.0));   // Mare Erythraeum
  dk += 0.6*exp(-pow(ang(p, dirOf(0.0,-4.0))/0.18,2.0));      // Sinus Meridiani
  dk += 0.5*exp(-pow(ang(p, dirOf(115.0,-20.0))/0.30,2.0));   // Mare Tyrrhenum / Cimmerium
  dk = clamp(dk * (0.75 + 1.1*fbm(p*4.0+3.0)), 0.0, 1.0);
  vec3 col = mix(bright, mid, smoothstep(0.1,0.7,fbm(p*5.0)+0.5));
  col = mix(col, dark, smoothstep(0.15,0.65,dk));
  col = mix(col, bright*1.08, 0.35*exp(-pow(ang(p, dirOf(-110.0,5.0))/0.45,2.0)));   // dusty Tharsis
  col *= 0.86 + 0.18*clamp(h*0.4,-1.0,1.0);
  col = mix(col, vec3(0.52,0.30,0.20), 0.35*smoothstep(-0.6,-1.6,h));               // deep basins darker/redder
  float capN = smoothstep(78.0, 84.0, lat + 3.0*fbm(p*8.0)), capS = smoothstep(-82.0, -86.0, lat - 2.5*fbm(p*8.0));
  col = mix(col, vec3(0.93,0.91,0.88), max(capN, capS*0.9));
  gl_FragColor = vec4(col, 1.0);
}`;

export function bakeMars(gl: THREE.WebGLRenderer, width = 2048) {
  const height = width / 2;
  const mk = () => { const t = new THREE.WebGLRenderTarget(width, height, { generateMipmaps: true, minFilter: THREE.LinearMipmapLinearFilter, magFilter: THREE.LinearFilter, colorSpace: THREE.SRGBColorSpace });
    t.texture.wrapS = THREE.RepeatWrapping; return t; };
  const colorRT = mk(), heightRT = mk();
  heightRT.texture.colorSpace = THREE.NoColorSpace;
  const mat = new THREE.ShaderMaterial({ uniforms: { uMode: { value: 0 } }, vertexShader: "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }", fragmentShader: FRAG });
  const scene = new THREE.Scene(); const cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat); scene.add(quad);
  const prev = gl.getRenderTarget();
  gl.setRenderTarget(colorRT); gl.render(scene, cam);
  mat.uniforms.uMode.value = 1; gl.setRenderTarget(heightRT); gl.render(scene, cam);
  gl.setRenderTarget(prev);
  mat.dispose(); quad.geometry.dispose();
  return { color: colorRT.texture, height: heightRT.texture };
}
