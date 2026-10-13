// Writes the test fixtures to stdout: CarrierDominion's own client/i18n.js (js/i18n.js) run on each case, with the
// game's real catalogues (js/en.json, js/no.json; a few keys are removed from the Norwegian one for the fallback).
// node js/make-fixtures.mjs > tests/FastengineTests/fixtures.json
import { readFileSync } from 'node:fs';
import { pickLang, createTranslator } from './i18n.js';

const read = ( f ) => JSON.parse( readFileSync( new URL( f, import.meta.url ), 'utf8' ) );
const en = read( './en.json' ), no = read( './no.json' );
const removed = [ 'seat.team', 'status.rejected', 'hud.locked', 'speed.vote' ];
for ( const k of removed ) delete no[ k ];

const picks = [];
for ( const requested of [ null, 'en', 'no', 'nb', 'de', 'EN', '' ] )
	for ( const nav of [ null, 'en-US', 'nb-NO', 'nn', 'no', 'NB-no', 'de-DE', 'n', '', 'sv' ] )
		picks.push( { requested, navigator: nav, lang: pickLang( requested ?? undefined, nav ?? undefined ) } );

const values = [ 3, 1.5, 0.1 + 0.2, - 7, 1e21, 2.5e-7, true, false, null, 'carrier {team}', 'æøå', '' ];
const keys = [ 'seat.team', 'status.rejected', 'hud.locked', 'speed.vote', 'status.tooFar', 'hangar.tally', 'no.such.key' ];
const translations = [];
for ( const lang of [ 'en', 'no' ] ) {
	const t = lang === 'en' ? createTranslator( en, en ) : createTranslator( no, en );
	for ( const key of keys ) {
		translations.push( { lang, key, vars: null, text: t( key ) } );
		const template = ( lang === 'en' ? en : no )[ key ] ?? en[ key ] ?? key;
		const names = [ ...template.matchAll( /\{(\w+)\}/g ) ].map( ( m ) => m[ 1 ] );
		values.forEach( ( v, i ) => {
			if ( names.length === 0 ) return;
			const vars = {};
			names.forEach( ( n, j ) => { vars[ n ] = values[ ( i + j ) % values.length ]; } );
			translations.push( { lang, key, vars, text: t( key, vars ) } );
		} );
	}
}
process.stdout.write( JSON.stringify( { removedFromNo: removed, picks, translations }, null, 1 ) + '\n' );
